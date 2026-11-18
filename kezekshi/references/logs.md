# Логтар: қайда және қалай

Бэкенд логтары JSON түрінде жазылады (`logback-spring.xml`), Kibana-да олар
`parsed_json.*` астында. Индекстер: `logs-*-*`, `logs-*`, `filebeat-*`.

## Өрістер

| Өріс | Не |
|---|---|
| `@timestamp` | уақыт, UTC (Алматы = +5 сағ) |
| `parsed_json.level` | INFO / WARN / ERROR |
| `parsed_json.message` | мәтін. Қателер: `[RequestID: …] ServiceException (4xx): …` |
| `parsed_json.requestId` | Request ID — пайдаланушыға қатеде көрінетін ID |
| `parsed_json.username`, `userId`, `userRoles` | кім жіберді |
| `parsed_json.requestHttpMethod`, `requestUri`, `requestMapping` | қай endpoint |
| `parsed_json.responseStatusCode` | HTTP статус |
| `parsed_json.duration` | жауап уақыты, мс |
| `parsed_json.X-Device-Name`, `app-version` | құрылғы, мобилка нұсқасы |
| `parsed_json.requestBody`, `responseBody` | **ШЫҒАРМА** — құпия деректер болуы мүмкін |

Әр сұранысқа бір «Request info» жолы жазылады. Сұраныс құласа, жанында сол
`requestId`-мен қате жолы болады.

## Іздеу реті

1. Скринде/өтініште Request ID бар → `--request-id`.
2. Жоқ → `--user <почта> --at "<өтініш уақыты>" --minutes 15 --errors`.
3. Ауқымы → `--mapping "<endpoint>" --since 1h --errors --count-users`.
4. «Тежеліп тұр» → `--user ... --since 1h` және `duration` бағанын қара.

## Ережелер

- Әрқашан уақыт шектеуімен ізде (скрипт өзі шектейді).
- Тек керекті өрістер шығады; сұраныс/жауап денесі, токен, пароль шықпайды.
- Kibana-ға қосылу болмаса (VPN жоқ / рұқсат жоқ) — кезекшіге Request ID мен уақытты
  беріп, әзірлеушіге тапсыруды ұсын.
