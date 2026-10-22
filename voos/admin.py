from django.contrib import admin, messages

from .models import Alerta, AvisoSistema, ConsultaPreco, Monitoramento
from .services import coletor


class ConsultaInline(admin.TabularInline):
    model = ConsultaPreco
    fields = ["consultado_em", "sucesso", "menor_preco", "companhia", "escalas", "data_ida", "provedor"]
    readonly_fields = fields
    extra = 0
    max_num = 0
    can_delete = False
    show_change_link = True

    def get_queryset(self, request):
        return super().get_queryset(request).order_by("-consultado_em")


@admin.register(Monitoramento)
class MonitoramentoAdmin(admin.ModelAdmin):
    list_display = ["__str__", "preco_alvo", "ultimo_preco", "menor_preco_visto", "ativo"]
    list_filter = ["ativo", "destino"]
    list_editable = ["ativo"]
    inlines = [ConsultaInline]
    actions = ["checar_agora"]

    @admin.display(description="último preço")
    def ultimo_preco(self, obj):
        c = obj.consultas.filter(menor_preco__isnull=False).first()
        return c.menor_preco if c else "—"

    @admin.display(description="menor já visto")
    def menor_preco_visto(self, obj):
        c = obj.consultas.filter(menor_preco__isnull=False).order_by("menor_preco").first()
        return c.menor_preco if c else "—"

    @admin.action(description="Checar preço agora")
    def checar_agora(self, request, queryset):
        resumo = coletor.executar(queryset)
        nivel = messages.WARNING if resumo["falhas"] else messages.SUCCESS
        self.message_user(
            request,
            f"{resumo['consultas']} consulta(s), {resumo['falhas']} falha(s), {resumo['alertas']} alerta(s).",
            nivel,
        )


@admin.register(ConsultaPreco)
class ConsultaPrecoAdmin(admin.ModelAdmin):
    list_display = ["monitoramento", "consultado_em", "sucesso", "menor_preco", "companhia", "provedor"]
    list_filter = ["sucesso", "provedor", "monitoramento"]
    readonly_fields = [f.name for f in ConsultaPreco._meta.fields]


@admin.register(AvisoSistema)
class AvisoSistemaAdmin(admin.ModelAdmin):
    list_display = ["chave", "enviado_em"]


@admin.register(Alerta)
class AlertaAdmin(admin.ModelAdmin):
    list_display = ["monitoramento", "criado_em", "motivos", "enviado"]
    list_filter = ["enviado"]
    readonly_fields = ["monitoramento", "consulta", "motivos", "enviado", "criado_em"]
