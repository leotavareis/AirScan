# Contexto do projeto (para continuar em outro PC)

Resumo da conversa de 21/10/2026 com o Claude Code. Para retomar, abra o projeto e peça:
"leia o CONTEXTO.md e vamos continuar o deploy".

## O que já está pronto

- **AirScan**: Django que monitora preços de passagens e avisa no Telegram (@Tavareisbot).
- **Provedores com fallback**: `fast_flights` (grátis) primeiro, `serpapi` como reserva.
  - Corrigido um bug da biblioteca fast-flights: ela só lia a seção "outros voos" do Google
    e perdia os mais baratos ("melhores voos"). Agora `voos/providers/fast_flights.py` lê as duas
    (ex.: GRU→LIS caiu de R$ 3.210 para R$ 2.205).
  - Página do Google sem voos é tratada como falha → passa para a SerpApi.
- **Limite da SerpApi**: plano grátis de 250 buscas/mês. Quando restarem `SERPAPI_RESERVA_MINIMA`
  (padrão 20), a reserva pausa e o Telegram avisa uma vez por mês. A cota aparece na tela de rotas.
  Em 21/10: 243 de 250 restantes.
- **Interface web** (`/`): login, lista de rotas, cadastro/edição/pausa/exclusão, histórico com
  gráfico, "Checar preço agora". Sugestões com 4.008 aeroportos (OurAirports) em `voos/data/`.
- **Alertas**: preço abaixo do alvo, queda de X% ou mínimo histórico; não repete sem nova queda.
  Aviso de falha no máximo 1x/dia.
- **Testes**: 41 passando (`python manage.py test voos`).
- **Agendamento no PC antigo (Windows)**: 3 tarefas "AirScan 07h/13h/20h" no Agendador,
  rodando `checar_precos.bat`. Elas continuam rodando naquele PC enquanto ele estiver ligado;
  apague-as quando o deploy na VM estiver funcionando (`schtasks /Delete /TN "AirScan 07h" /F` etc.).

## Observações importantes

- A rota NAT→IGU (set/2027, ±3 dias) quase nunca funciona no fast-flights (o Google não entrega
  os voos para essa busca) e depende da SerpApi: 7 buscas por checagem. Com o limite ela não estoura
  a cota, mas fica sem preço depois de ~11 dias. Reduzir o flex para 0–1 resolve.
- O Python usado é 3.14; o Django 6 exige 3.12+.

## O que NÃO está no GitHub (copie à mão se quiser)

- `.env`: tokens do Telegram, chave da SerpApi, chave secreta do Django e o chat id. Use
  `.env.example` como modelo. **Não envie o `.env` para o GitHub.**
- `db.sqlite3`: rotas e histórico. Copie se quiser manter os dados, ou recadastre.

Para montar o ambiente no outro PC:

```bash
git clone https://github.com/leotavareis/AirScan.git
cd AirScan
py -3.14 -m venv .venv
.venv\Scripts\pip install -r requirements.txt
copy .env.example .env   (e preencha, ou copie o .env do PC antigo)
.venv\Scripts\python manage.py migrate
.venv\Scripts\python manage.py createsuperuser   (se não copiou o db.sqlite3)
```

## Próximo passo: deploy na VM da Oracle

Decisão: hospedar na VM Oracle que já roda o sistema de `tzurapp.com.br`, **totalmente isolado**,
para poder remover sem afetar o sistema existente. (Vercel foi descartado: sem disco persistente,
tempo de execução curto e cron só 1x/dia no plano grátis.)

- VM: IP **147.15.49.224**, já com nginx e HTTPS para `tzurapp.com.br` e `www`.
- DNS no **Registro.br** (`a.auto.dns.br`), grátis.
- Endereço do AirScan: **`airscan.tzurapp.com.br`**.

### Plano de isolamento

| Peça | Onde fica |
|---|---|
| Usuário Linux | `airscan` (separado) |
| Código, banco, `.env` | `/home/airscan/AirScan` |
| Python | instalado só para o usuário `airscan` via `uv` (não mexe no Python do sistema) |
| App | Gunicorn em `127.0.0.1:8010` |
| Serviço | `airscan.service` (systemd, arquivo novo) |
| Checagens 3x/dia | crontab do usuário `airscan` |
| Nginx | arquivo novo `sites-available/airscan` (não edita o do tzurapp) |
| HTTPS | certbot só para `airscan.tzurapp.com.br` |
| Remoção | script `deploy/desinstalar.sh` |

### Situação em 01/11/2026

Instalado na VM com `bash deploy/enviar.sh` (banco começou do zero). App ativo em `127.0.0.1:8010`,
checagens nos horários definidos no site em /horarios/ (timer a cada 5 min roda `checar_precos --agendado`), tokens copiados, Telegram testado, fast-flights
funciona a partir do IP da Oracle. Diferenças do plano: timer do systemd em vez de crontab, estáticos em
`/var/www/airscan/static`. A porta 443 pública é do **sslh** (repassa TLS para o nginx em `127.0.0.1:8443`),
por isso o certificado é `certbot certonly --webroot`, nunca `--nginx`.

Falta: (a) registro DNS `airscan` propagar (modo avançado do Registro.br em transição) e rodar
`bash deploy/enviar.sh` de novo para gerar o HTTPS; (b) criar o login com `createsuperuser` na VM;
(c) recadastrar as rotas; (d) apagar as tarefas do PC antigo.

### Pendências (histórico de 21/10)

1. **Você**: criar no Registro.br (Editar zona) o registro `A`, nome `airscan`, valor `147.15.49.224`.
2. **Você**: mandar a saída deste comando rodado na VM:
   ```bash
   cat /etc/os-release | head -3; uname -m; python3 --version; nginx -v; ls /etc/nginx/sites-enabled/ /etc/nginx/conf.d/
   ```
3. **Você**: decidir se leva o `db.sqlite3` (rotas/histórico) ou começa do zero na VM.
4. **Você**: dizer se o Claude terá acesso SSH à VM ou se você roda os comandos.
5. **Claude**: ajustes de produção no projeto (DEBUG/ALLOWED_HOSTS/CSRF_TRUSTED_ORIGINS pelo `.env`,
   `SECURE_PROXY_SSL_HEADER`, `collectstatic` servido pelo nginx, gunicorn no requirements) e a pasta
   `deploy/` com serviço systemd, config do nginx, script de instalação e de remoção.
6. Depois do deploy: apagar as tarefas agendadas do PC antigo e conferir se o fast-flights funciona
   a partir do IP da Oracle (se falhar mais, a SerpApi cobre dentro do limite).
