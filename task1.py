# 1) Основная проблема была это тяжеловесность вьюх и плохая производительность, из-за множества фильтров и ненужных конструкций
# ----fix: Был создан класс с оптимизированной логикой фильтрации, используя Q конкатинацию параметров
# 2) Нарушение принципа единственной ответственности во вьюхах, например кроме самих листов отдают количество элементов
# ----fix: Каунты вынесены в отдельные вьюхи, с переиспользованием логики фильтрации, выглядит лаконично и понятно.
# Я бы еще кастомеров вынес, но там что-то специфичное может быть на фронте, поэтому оставил.
# 3) Путаница в данных respons'ов, разные сущности были зачем то перемешаны в zip.
# OrderList имеет фильтр для favorites заказов, и зачем-то еще возвращал их в response
# ----fix: Сделал понятный dict, убрал zip, убрал favorites из OrderList(пусть пользуются фильтром)
# 4) Нарушение наименования переменных, в переменных нет snake_case, в классах CamelCase
# ----fix: Были переименованы, кроме классов из .models

from django.db.models import Q
from django.http import JsonResponse
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import render
from django.views.generic import View
from .models import Orders, Comments, CustomersList, Orderresponsible, Ordercomresponsible, Costs, Approvedlists, Favorites
from datetime import date


class SearchMixin:
    def build_order_filter(self):
        search = self.request.user.search
        filter_conditions = Q()

        if search.search:
            filter_conditions &= Q(name__icontains=search.search) | Q(searchowners__icontains=search.search)
        else:
            if search.goal:
                filter_conditions &= Q(goal=True)
            if search.favorite:
                favorites_ids = Favorites.objects.filter(user=self.request.user).values_list('order__orderid',
                                                                                             flat=True)
                filter_conditions &= Q(orderid__in=favorites_ids)
            if search.manager:
                responsible_order_ids = Orderresponsible.objects.filter(user=search.manager).values_list(
                    'orderid__orderid', flat=True)
                com_responsible_order_ids = Ordercomresponsible.objects.filter(user=search.manager).exclude(
                    orderid__orderid__in=responsible_order_ids).values_list('orderid__orderid', flat=True)
                filter_conditions &= Q(orderid__in=list(responsible_order_ids) + list(com_responsible_order_ids))
            if search.stage:
                filter_conditions &= Q(stageid=search.stage)
            if search.company:
                filter_conditions &= Q(Q(cityid=None) | Q(cityid=search.company))
            if search.customer:
                filter_conditions &= Q(searchowners__icontains=search.customer)

        return filter_conditions

    def build_cost_filter(self):
        search = self.request.user.search
        filter_conditions = Q()

        if search.search:
            filter_conditions &= (
                    Q(description__icontains=search.search) |
                    Q(section__icontains=search.search) |
                    Q(orderid__name__icontains=search.search)
            )
        else:
            if search.goal:
                filter_conditions &= Q(orderid__goal=True)
            if search.favorite:
                favorite_orders_ids = Favorites.objects.filter(user=self.request.user).values_list('order__orderid',
                                                                                                   flat=True)
                filter_conditions &= Q(orderid__in=favorite_orders_ids)
            if search.manager:
                filter_conditions &= Q(user=search.manager)
            if search.stage:
                filter_conditions &= Q(orderid__stageid=search.stage)
            if search.company:
                filter_conditions &= Q(Q(orderid__cityid=None) | Q(orderid__cityid=search.company))
            if search.customer:
                filter_conditions &= Q(orderid__searchowners__icontains=search.customer)

        return filter_conditions


class OrderCount(LoginRequiredMixin, SearchMixin, View):
    def get(self, request):
        orders = Orders.objects.filter(self.build_order_filter())
        return JsonResponse({'count': orders.count()})


class OrderList(LoginRequiredMixin, SearchMixin, View):
    def get(self, request):
        orders = Orders.objects.filter(self.build_order_filter())
        orders = orders.order_by('-reiting')[int(request.GET['start']):int(request.GET['stop'])]

        orders = orders.prefetch_related('customerslist_set__customerid', 'orderresponsible_set')
        customers = CustomersList.objects.filter(orderid__in=[o.orderid for o in orders]).order_by('customerid__title')
        last_contact = [
            Comments.objects.filter(orderid=o).first().createdat if Comments.objects.filter(orderid=o).exists() else ''
            for o in orders]
        responsible_orders = Orderresponsible.objects.filter(orderid__in=[o.orderid for o in orders])

        return render(request, 'main/orders_list.html', {
            'orders': orders,
            'responsible_orders': responsible_orders,
            'customers': customers,
            'last_contact': last_contact,
            'today': date.today()
        })


class CostCount(LoginRequiredMixin, SearchMixin, View):
    def get(self, request):
        costs = Costs.objects.filter(self.build_cost_filter())
        return JsonResponse({'count': costs.count()})


class CostList(LoginRequiredMixin, SearchMixin, View):
    def get(self, request):
        costs = Costs.objects.filter(self.build_cost_filter())
        costs = costs.order_by('-createdat')[int(request.GET['start']):int(request.GET['stop'])]
        costs = costs.prefetch_related('approvedlists_set')

        return render(request, 'main/cost_list.html', {
            'costs': costs,
            'approved': Approvedlists.objects.filter(cost_id__in=costs),
            'today': date.today()
        })

