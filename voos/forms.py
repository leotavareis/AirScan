from django import forms
from django.utils import timezone

from .models import Agenda, Monitoramento


class AgendaForm(forms.ModelForm):
    class Meta:
        model = Agenda
        fields = ["horario_1", "horario_2", "horario_3"]
        widgets = {
            campo: forms.TimeInput(attrs={"type": "time"}, format="%H:%M")
            for campo in ["horario_1", "horario_2", "horario_3"]
        }

    def clean(self):
        dados = super().clean()
        horarios = [dados.get(c) for c in self.Meta.fields if dados.get(c)]
        if len(set(horarios)) != len(horarios):
            raise forms.ValidationError("Os horários precisam ser diferentes.")
        return dados


class MonitoramentoForm(forms.ModelForm):
    class Meta:
        model = Monitoramento
        fields = [
            "origem",
            "destino",
            "data_ida",
            "data_volta",
            "flex_dias",
            "adultos",
            "classe",
            "preco_alvo",
            "queda_percentual",
            "ativo",
        ]
        labels = {
            "data_ida": "Data de ida",
            "data_volta": "Data de volta",
            "flex_dias": "Flexibilidade (± dias)",
            "preco_alvo": "Preço alvo (R$)",
            "queda_percentual": "Avisar se cair (%)",
        }
        widgets = {
            "origem": forms.TextInput(attrs={"list": "aeroportos", "placeholder": "GRU", "autocomplete": "off"}),
            "destino": forms.TextInput(attrs={"list": "aeroportos", "placeholder": "LIS", "autocomplete": "off"}),
            "data_ida": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
            "data_volta": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
            "flex_dias": forms.NumberInput(attrs={"min": 0, "max": 3}),
            "adultos": forms.NumberInput(attrs={"min": 1, "max": 9}),
            "preco_alvo": forms.NumberInput(attrs={"step": "1", "min": 0, "placeholder": "4000"}),
            "queda_percentual": forms.NumberInput(attrs={"min": 0, "max": 90}),
        }

    def _codigo(self, campo):
        valor = self.cleaned_data[campo].strip().upper()
        if len(valor) != 3 or not valor.isalpha():
            raise forms.ValidationError("Use o código de 3 letras do aeroporto (ex.: GRU).")
        return valor

    def clean_origem(self):
        return self._codigo("origem")

    def clean_destino(self):
        return self._codigo("destino")

    def clean_data_ida(self):
        data = self.cleaned_data["data_ida"]
        if data < timezone.localdate() and data != self.initial.get("data_ida"):
            raise forms.ValidationError("A data de ida já passou.")
        return data

    def clean_flex_dias(self):
        dias = self.cleaned_data["flex_dias"]
        if dias > 3:
            raise forms.ValidationError("Máximo de 3 dias: cada dia a mais é uma busca a mais.")
        return dias
