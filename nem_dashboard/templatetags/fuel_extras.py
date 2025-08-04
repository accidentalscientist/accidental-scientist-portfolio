from django import template

register = template.Library()

@register.filter
def get_fuel_icon(fuel_type, icon_dict):
    return icon_dict.get(fuel_type, '❓')  # Default fallback
