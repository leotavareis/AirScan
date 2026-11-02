from datetime import time

from django.core.exceptions import ValidationError
from django.db import models


class Monitoramento(models.Model):
    CLASSES = [
        ("economy", "Econômica"),
        ("premium-economy", "Econômica premium"),
        ("business", "Executiva"),
        ("first", "Primeira classe"),
    ]

    origem = models.CharField(max_length=3, help_text="Código IATA, ex.: GRU")
    destino = models.CharField(max_length=3, help_text="Código IATA, ex.: LIS")
    data_ida = models.DateField()
    data_volta = models.DateField(null=True, blank=True, help_text="Vazio = só ida")
    flex_dias = models.PositiveSmallIntegerField(
        default=0, help_text="Também busca ±N dias em volta da ida (cada dia é uma busca a mais)"
    )
    adultos = models.PositiveSmallIntegerField(default=1)
    classe = models.CharField(max_length=20, choices=CLASSES, default="economy")
    preco_alvo = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True, help_text="Avisa quando ficar abaixo deste valor"
    )
    queda_percentual = models.PositiveSmallIntegerField(
        default=10, help_text="Avisa se cair pelo menos X% desde a última consulta (0 = desliga)"
    )
    ativo = models.BooleanField(default=True)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "monitoramento"
        ordering = ["data_ida"]

    def __str__(self):
        volta = f" ↔ {self.data_volta:%d/%m}" if self.data_volta else ""
        return f"{self.origem} → {self.destino} em {self.data_ida:%d/%m/%Y}{volta}"

    def clean(self):
        self.origem = self.origem.upper().strip()
        self.destino = self.destino.upper().strip()
        if self.origem and self.origem == self.destino:
            raise ValidationError("Origem e destino não podem ser iguais.")
        if self.data_volta and self.data_ida and self.data_volta < self.data_ida:
            raise ValidationError({"data_volta": "A volta precisa ser depois da ida."})

    def save(self, *args, **kwargs):
        self.origem = self.origem.upper().strip()
        self.destino = self.destino.upper().strip()
        super().save(*args, **kwargs)


class ConsultaPreco(models.Model):
    monitoramento = models.ForeignKey(Monitoramento, on_delete=models.CASCADE, related_name="consultas")
    consultado_em = models.DateTimeField(auto_now_add=True)
    sucesso = models.BooleanField(default=True)
    provedor = models.CharField(max_length=30, blank=True)
    menor_preco = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    moeda = models.CharField(max_length=3, default="BRL")
    companhia = models.CharField(max_length=200, blank=True)
    escalas = models.PositiveSmallIntegerField(null=True, blank=True)
    data_ida = models.DateField(null=True, blank=True, help_text="Data em que o menor preço foi achado")
    data_volta = models.DateField(null=True, blank=True)
    erro = models.TextField(blank=True)
    dados_brutos = models.JSONField(default=dict, blank=True)

    class Meta:
        verbose_name = "consulta de preço"
        verbose_name_plural = "consultas de preço"
        ordering = ["-consultado_em"]

    def __str__(self):
        if not self.sucesso:
            return f"{self.monitoramento} — falhou"
        return f"{self.monitoramento} — {self.moeda} {self.menor_preco}"


class Agenda(models.Model):
    """Horários das checagens automáticas (horário de Brasília). Tabela de uma linha só."""

    MAXIMO = 3  # limite das ferramentas de busca (cota da SerpApi)

    horario_1 = models.TimeField("1º horário", default=time(7, 5))
    horario_2 = models.TimeField("2º horário", null=True, blank=True, default=time(13, 10))
    horario_3 = models.TimeField("3º horário", null=True, blank=True, default=time(20, 15))

    class Meta:
        verbose_name = "agenda das checagens"
        verbose_name_plural = "agenda das checagens"

    def __str__(self):
        return ", ".join(f"{h:%H:%M}" for h in self.horarios())

    @classmethod
    def atual(cls) -> "Agenda":
        return cls.objects.get_or_create(pk=1)[0]

    def horarios(self) -> list[time]:
        return sorted(h for h in (self.horario_1, self.horario_2, self.horario_3) if h is not None)


class AvisoSistema(models.Model):
    """Avisos do sistema já enviados (cota, falhas), para não repetir no mesmo período."""

    chave = models.CharField(max_length=100, unique=True)
    enviado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "aviso do sistema"
        verbose_name_plural = "avisos do sistema"

    def __str__(self):
        return self.chave


class Alerta(models.Model):
    monitoramento = models.ForeignKey(Monitoramento, on_delete=models.CASCADE, related_name="alertas")
    consulta = models.ForeignKey(ConsultaPreco, on_delete=models.CASCADE, related_name="alertas")
    motivos = models.JSONField(default=list)
    enviado = models.BooleanField(default=False)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-criado_em"]

    def __str__(self):
        return f"{self.monitoramento} — {', '.join(self.motivos)}"
