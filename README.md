# JUZ40 кезекші скиллдері

Кезекшілікке кез келген адам — әзірлеуші болмаса да — отыра алуы үшін Claude скиллдері.

| Скилл | Не істейді |
|---|---|
| [`kezekshi`](kezekshi/SKILL.md) | Чаттан түскен өтінішті қадаммен өңдейді: қабылдау → қайталау (браузер арқылы да) → диагностика → шешім мен жауап → Jira/білім қоры → журнал және кешкі дейли-репорт |
| [`bag-jira`](bag-jira/SKILL.md) | Багты ауқымымен, қадамдарымен және дәлелімен Jira тапсырмасына айналдырады |
| [`tg`](tg/SKILL.md) | `/tg`: чаттағы өтінішті жеке Telegram-ботқа пересылка жасайсың — ол Claude сессиясына түседі (мәтін, фото, файл) |
| [`datagrip-readonly`](datagrip-readonly/SKILL.md) | DataGrip MCP арқылы базаны тек оқу ережесі: INSERT/UPDATE/DELETE жібермейді, SQL-ды кезекшіге дайындап береді |

Сессияда қорғауға арналған черновик: [docs/strat-session-draft.md](docs/strat-session-draft.md).

## Орнату

```bash
git clone <осы репо>
ln -s "$(pwd)/kezekshi-skills/kezekshi" ~/.claude/skills/kezekshi
ln -s "$(pwd)/kezekshi-skills/bag-jira" ~/.claude/skills/bag-jira
ln -s "$(pwd)/kezekshi-skills/tg" ~/.claude/skills/tg
ln -s "$(pwd)/kezekshi-skills/datagrip-readonly" ~/.claude/skills/datagrip-readonly
```

Telegram-ботты бір рет баптау (токенді тек өзің енгізесің, ол `~/.claude/tg-inbox/`-те сақталады, репода емес):

```bash
python3 ~/.claude/skills/tg/tg_inbox.py setup
```

Claude Code-ты қайта аш — скиллдер тізімде шығады.

## Көздерді қосу (бар болғанынша)

| Көз | Не керек |
|---|---|
| Код | бэкенд, фронт, мобилка репозиторийлері жергілікті (Claude сессиясы солардың қасында ашылады) |
| Логтар | **Ұсынылады:** `juz40-vpn-logs` сервисі — `export LOGS_SERVICE_URL=https://<logs-host>` және `LOGS_SERVICE_TOKEN=<токен>` (VPN керек емес). **Немесе:** VPN + `export KIBANA_URL=http://<kibana-host>:5601`. Айнымалыларды `~/.zshrc`-ке қос. Тексеру: `python3 kezekshi/scripts/logs.py --check` |
| Браузер | Claude қосымшасындағы браузер немесе Claude in Chrome — пайдаланушы аккаунтын қарау үшін (админ кіруі мен impersonation құпия сөзін кезекші өзі енгізеді) |
| Журнал | автоматты: `~/.kezekshi/journal/` (репода емес). Репорт сағаты: `KEZEKSHI_REPORT_HOUR` (әдепкі 18) |
| Дерекқор | тек оқу рұқсаты бар қосылым (DB MCP). Жазу рұқсаты кезекшіге берілмейді |
| Jira | Atlassian MCP |

Көз қосылмаса да скилл жұмыс істейді — бірақ қолжетімсіз көз бойынша «әзірлеушіге
тапсыр, мынаны тексерсін» дейді.

## Қауіпсіздік

- Скилл продта **ештеңе өзгертпейді**: түзетуді дайындайды, әзірлеуші растап орындайды.
- Чаттағы пароль/токен қолданылмайды; логтан сұраныс денесі шығарылмайды.
- Бұл репода құпия деректер (мекенжай, кілт, почта) сақталмайды — бәрі ортаның айнымалыларында.

## Скиллді толықтыру

Жаңа қайталанатын жағдай → `kezekshi/references/cases.md`-ге (үлгі ішінде).
Қадам ережесін өзгерту → `kezekshi/steps/*.md`. Өзгерістерді MR арқылы.
