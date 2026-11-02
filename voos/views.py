from django.conf import settings
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Min, OuterRef, Subquery
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.views import View
from django.views.generic import CreateView, DeleteView, DetailView, ListView, UpdateView

from .aeroportos import AEROPORTOS
from .forms import AgendaForm, MonitoramentoForm
from .models import Agenda, ConsultaPreco, Monitoramento
from .providers import serpapi
from .services import agenda, coletor


class MonitoramentoLista(LoginRequiredMixin, ListView):
    model = Monitoramento
    template_name = "voos/lista.html"
    context_object_name = "monitoramentos"

    def get_queryset(self):
        ultima = ConsultaPreco.objects.filter(monitoramento=OuterRef("pk"), menor_preco__isnull=False).order_by(
            "-consultado_em"
        )
        return (
            Monitoramento.objects.annotate(
                ultimo_preco=Subquery(ultima.values("menor_preco")[:1]),
                ultima_consulta=Subquery(ultima.values("consultado_em")[:1]),
                menor_visto=Min("consultas__menor_preco"),
            )
            .order_by("-ativo", "data_ida")
        )

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["cota_serpapi"] = serpapi.consultar_cota()
        ctx["reserva_minima"] = settings.SERPAPI_RESERVA_MINIMA
        ctx["agenda"] = Agenda.atual()
        ctx["proxima_checagem"] = agenda.proximo_horario()
        return ctx


class MonitoramentoDetalhe(LoginRequiredMixin, DetailView):
    model = Monitoramento
    template_name = "voos/detalhe.html"
    context_object_name = "m"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        consultas = self.object.consultas.all()[:200]
        com_preco = [c for c in reversed(consultas) if c.menor_preco is not None]
        ctx["consultas"] = consultas[:30]
        ctx["ultimo_preco"] = com_preco[-1].menor_preco if com_preco else None
        ctx["alertas"] = self.object.alertas.select_related("consulta")[:10]
        ctx["grafico"] = {
            "labels": [timezone.localtime(c.consultado_em).strftime("%d/%m %Hh") for c in com_preco],
            "precos": [float(c.menor_preco) for c in com_preco],
            "alvo": float(self.object.preco_alvo) if self.object.preco_alvo else None,
        }
        return ctx


class AgendaEditar(LoginRequiredMixin, UpdateView):
    form_class = AgendaForm
    template_name = "voos/agenda.html"
    success_url = reverse_lazy("voos:lista")

    def get_object(self, queryset=None):
        return Agenda.atual()

    def form_valid(self, form):
        resposta = super().form_valid(form)
        messages.success(self.request, f"Horários das checagens salvos: {self.object}.")
        return resposta


class MonitoramentoMixin(LoginRequiredMixin):
    model = Monitoramento
    form_class = MonitoramentoForm
    template_name = "voos/form.html"
    extra_context = {"aeroportos": AEROPORTOS}

    def get_success_url(self):
        return reverse("voos:detalhe", args=[self.object.pk])


class MonitoramentoCriar(MonitoramentoMixin, CreateView):
    def form_valid(self, form):
        messages.success(self.request, "Rota cadastrada. Ela entra na próxima checagem agendada.")
        return super().form_valid(form)


class MonitoramentoEditar(MonitoramentoMixin, UpdateView):
    def form_valid(self, form):
        messages.success(self.request, "Rota atualizada.")
        return super().form_valid(form)


class MonitoramentoExcluir(LoginRequiredMixin, DeleteView):
    model = Monitoramento
    template_name = "voos/excluir.html"
    context_object_name = "m"
    success_url = reverse_lazy("voos:lista")

    def form_valid(self, form):
        messages.success(self.request, f"Rota {self.object} excluída.")
        return super().form_valid(form)


class MonitoramentoChecar(LoginRequiredMixin, View):
    def post(self, request, pk):
        m = get_object_or_404(Monitoramento, pk=pk)
        resumo = coletor.executar([m])
        if resumo["falhas"]:
            messages.error(request, "Nenhum provedor respondeu. Veja o erro no histórico.")
        elif m.consultas.first().menor_preco is None:
            messages.warning(
                request,
                "O Google Voos não mostrou nenhum voo para essas datas. "
                "Se a viagem for daqui a muitos meses, as companhias podem ainda não ter aberto as vendas.",
            )
        else:
            consulta = m.consultas.first()
            texto = f"Menor preço agora: {coletor.formatar_preco(consulta.menor_preco, consulta.moeda)}"
            if resumo["alertas"]:
                texto += " — alerta enviado no Telegram."
            messages.success(request, texto)
        return redirect("voos:detalhe", pk=pk)


class MonitoramentoAlternar(LoginRequiredMixin, View):
    def post(self, request, pk):
        m = get_object_or_404(Monitoramento, pk=pk)
        m.ativo = not m.ativo
        m.save(update_fields=["ativo"])
        messages.success(request, f"{m} {'reativada' if m.ativo else 'pausada'}.")
        return redirect(request.POST.get("next") or "voos:lista")
