# AirScan

Monitora preços de passagens e avisa no Telegram quando baixam.

- **Provedores, em ordem:** `fast_flights` (Google Voos, grátis) → `serpapi` (reserva, usa a cota grátis da SerpApi). Se o primeiro falhar ou não trouxer nada, o segundo é usado. Se todos falharem, você recebe um aviso no Telegram.
- **Avisa quando:** o preço fica abaixo do alvo, cai X% desde a última consulta ou bate o menor valor já visto. Só avisa de novo se o preço cair abaixo do último aviso.

## Instalação

```bash
py -3.14 -m venv .venv
.venv\Scripts\pip install -r requirements.txt
copy .env.example .env
.venv\Scripts\python manage.py migrate
.venv\Scripts\python manage.py createsuperuser
```

## Telegram

1. No Telegram, fale com o **@BotFather**, use `/newbot` e copie o token para `TELEGRAM_BOT_TOKEN` no `.env`.
2. Mande qualquer mensagem para o seu bot.
3. Rode `python manage.py telegram_teste`: ele mostra o seu chat id. Coloque em `TELEGRAM_CHAT_ID`.
4. Rode `telegram_teste` de novo para receber a mensagem de teste.

## Uso

- `python manage.py runserver` e acesse http://127.0.0.1:8000 para cadastrar, editar, pausar e excluir rotas, ver o gráfico do histórico e checar o preço na hora. O admin do Django continua em `/admin`.
- `python manage.py checar_precos` roda todos os ativos (`--id 3` para só um, `--sem-notificar` para testar sem mandar nada).
- `python manage.py test voos` roda os testes.

Cada dia de `flex_dias` é uma busca a mais; tenha isso em mente se a SerpApi entrar em ação (a cota grátis é pequena).
Quando restarem `SERPAPI_RESERVA_MINIMA` buscas (padrão 20), a SerpApi é pausada até a cota renovar e você recebe um aviso no Telegram (uma vez por mês). A cota restante aparece na tela de rotas.

## Agendamento (3x por dia)

**Windows** (Agendador de Tarefas), em um terminal:

```bat
schtasks /Create /TN "AirScan 07h" /TR "C:\AirScan\checar_precos.bat" /SC DAILY /ST 07:05
schtasks /Create /TN "AirScan 13h" /TR "C:\AirScan\checar_precos.bat" /SC DAILY /ST 13:10
schtasks /Create /TN "AirScan 20h" /TR "C:\AirScan\checar_precos.bat" /SC DAILY /ST 20:15
```

O log fica em `logs\checar_precos.log`.

**Linux** (`crontab -e`):

```
5 7,13,20 * * * cd /caminho/AirScan && .venv/bin/python manage.py checar_precos >> logs/checar_precos.log 2>&1
```
