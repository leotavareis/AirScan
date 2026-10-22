from django import template

from voos.services.coletor import formatar_preco

register = template.Library()


@register.filter
def brl(valor):
    if valor is None or valor == "":
        return "—"
    return formatar_preco(valor)
