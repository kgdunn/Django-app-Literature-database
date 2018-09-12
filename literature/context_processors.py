from django.conf import settings


def global_template_variables(request):
    return { 'ANALYTICS_SNIPPET': settings.DEFAULTS['analytics_snippet'],
             'VERSION': settings.DEFAULTS['version'],
            }