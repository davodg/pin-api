# Pin-api

[English](README.md) | **Português (Brasil)**

Essa API faz operações CRUD em um banco de dados Postgres. Abaixo, vamos entender cada endpoint.

## Requisitos
- Python
- Docker

## Autenticação e autorização

A demonstração representa uma única organização e deve usar apenas dados fictícios.
Todos os endpoints `/api/v1/feedback` exigem `Authorization: Bearer <token>`.

| Perfil | GET | POST / PUT / PATCH / DELETE |
| --- | --- | --- |
| `viewer` | Permitido | Proibido |
| `admin` | Permitido | Permitido |

`/`, `/health`, `/docs` e `/openapi.json` são públicos. O login é `POST /auth/token`.
A ausência de credenciais, token inválido/expirado ou usuário desativado resulta em
`401`; falta de permissão resulta em `403`. O perfil e o estado do usuário são lidos
do banco a cada requisição. Não há cadastro público, refresh token ou logout com
revogação individual: o token expira após 15 minutos. Desativar o usuário invalida
seu acesso imediatamente; trocar `JWT_SECRET` invalida todos os tokens.

### Configuração inicial

1. Copie `.env.example` para `.env` e ajuste `DB_*` para o seu PostgreSQL.
2. Gere um segredo aleatório e defina `JWT_SECRET` no `.env` (não versione o valor):

   ```bash
   python -c "import secrets; print(secrets.token_urlsafe(48))"
   ```

3. Instale as dependências e aplique as migrations, incluindo a tabela de usuários:

   ```bash
   python -m pip install -r requirements.txt
   dotenv run -- alembic upgrade head
   ```

4. Crie os usuários; a senha será solicitada sem eco e deve ter 12–128 caracteres:

   ```bash
   python -m app.create_user --username demo --role viewer
   python -m app.create_user --username administrador --role admin
   ```

O comando não sobrescreve usuários existentes. Senhas são armazenadas como hashes
Argon2id; cálculo e verificação são executados fora do event loop. A aplicação
recusa iniciar sem um `JWT_SECRET` de pelo menos 32 bytes. No Docker, execute os
comandos de migration e criação de usuários dentro do serviço `pin-api`, usando
`docker compose exec pin-api ...`, após configurar `.env` e iniciar o banco.

### Login e uso

Envie JSON para `POST /auth/token`:

```json
{"username": "demo", "password": "sua-senha"}
```

Resposta: `access_token`, `token_type: "bearer"` e `expires_in: 900`.
No Swagger (`/docs`), execute o login e cole `access_token` em **Authorize**.
Nos exemplos curl abaixo, acrescente `-H "Authorization: Bearer $TOKEN"`.

O login permite 10 tentativas por IP em uma janela de 60 segundos, inclusive
logins bem-sucedidos. O limite é persistido no PostgreSQL e compartilhado pelos
workers; excesso retorna `429` com `Retry-After: 60`. Registros com mais de um dia
são removidos durante novas tentativas. Atrás de proxy, configure o servidor ASGI
para confiar apenas nos IPs do seu proxy; não confie em forwarded headers de
clientes arbitrários. Usuários atrás do mesmo IP compartilham esse limite.

No deploy público, configure HTTPS no proxy/plataforma, mantenha a conta `admin`
privada e divulgue apenas a conta `viewer` com dados fictícios. HTTPS não é
configurado por este repositório. A política atual permite consultar todos os
feedbacks da organização; não implementa isolamento entre empresas ou autorização
por proprietário do registro.

## Idempotência na criação

`POST /api/v1/feedback` e `POST /api/v1/feedback/batch` exigem o header `Idempotency-Key`. Gere uma chave por
operação (recomendado: UUID) e reutilize-a em todas as tentativas daquela operação.
Aceitamos 1–128 caracteres: letras ASCII, números, ponto, hífen, `_` e `:`.
Ausência ou formato inválido retorna `422`.

```bash
curl -X POST http://127.0.0.1:8000/api/v1/feedback \
  -H "Authorization: Bearer $TOKEN" \
  -H "Idempotency-Key: 752e2068-fdad-4385-a95c-b6427d43692c" \
  -H "Content-Type: application/json" --data-binary @feedback.json
```

- Mesma chave, usuário e payload: retorna o status `200` e o JSON originais,
  inclusive se o feedback já tiver sido alterado ou excluído.
- Mesma chave e usuário, mas outro payload: `409 Conflict`.
- Usuários diferentes possuem espaços de chaves independentes.
- Payloads são validados pelo Pydantic antes do hash SHA-256. A ordem das chaves
  JSON não importa; campos opcionais omitidos equivalem aos respectivos defaults.
- A retenção é de 24 horas a partir da gravação da resposta. Repetições não
  renovam esse prazo. Após expirar, reutilizar a chave pode criar outro feedback.
- A reserva, o feedback e a resposta são gravados na mesma transação. Falhas
  antes do commit desfazem tudo e permitem repetir a mesma chave.
- Requisições concorrentes aguardam o PostgreSQL. O limite de espera por lock
  é de 3 segundos; ao excedê-lo, retornamos `503` com `Retry-After: 1`.
  Repita usando a mesma chave, sem gerar outra.
- Autenticação e autorização são verificadas em toda tentativa, antes do replay.
  Erros de validação e respostas de erro não são armazenados.

Aplique a migration `0004` com `dotenv run -- alembic upgrade head` antes de subir
a versão atualizada. A tabela armazena uma cópia do feedback na resposta JSONB;
use os mesmos controles de acesso e backup do restante do banco.

Para remover respostas expiradas, execute periodicamente:

```bash
python -m app.cleanup_idempotency
```

A limpeza remove lotes de até 1.000 registros, ignora linhas bloqueadas por
requisições ativas e não exclui os feedbacks. Nenhum agendamento é criado
automaticamente. A expiração lógica funciona mesmo antes da limpeza física.
Chaves diferentes não impedem duplicatas de negócio. PUT, PATCH e DELETE
não usam esse mecanismo de replay.

## Validação de feedbacks

Os modelos Pydantic documentam o payload em `/docs` e rejeitam entradas inválidas
com `422`, antes de executar SQL. POST e PUT exigem `name`, `email`,
`corporate_email`, `department`, `location`, `company_tenure`, `gender`,
`generation` e as oito notas (`interest_in_position`, `contribution`,
`learning_and_development`, `feedback`, `manager_interaction`,
`opportunity_clarity`, `permanence_expectation`, `enps`).

- Textos obrigatórios não podem ser vazios e respeitam os limites das colunas.
- E-mails são validados; campos desconhecidos e `id` no body são rejeitados.
- Notas devem ser inteiros JSON, sem coerção de strings, booleanos ou decimais.
  Os limites são os do INTEGER do PostgreSQL; não há escala de questionário definida.
- Datas de entrada e saída usam `YYYY-MM-DD`. O antigo formato `DD/MM/YYYY`
  não é mais aceito. A coluna TIMESTAMP existente é mantida; a API expõe a data.
- Identificadores de rota e filtro `id` devem ser UUIDs válidos.

Não há migration de banco nesta alteração. Registros preexistentes precisam
atender ao contrato de resposta (inclusive e-mails válidos e textos obrigatórios).
Clientes que enviavam PUT parcial devem passar a usar PATCH.

## Endpoints

### POST /api/v1/feedback

Cria um registro na tabela `employee_feedback`. Requer `Idempotency-Key` conforme a seção de idempotência.

**Body (JSON) – exemplo:**
```json
{
  "name": "Demo 019",
  "email": "demo019@pinpeople.com.br",
  "phone_number": "11912488394",
  "corporate_email": "demo019@pinpeople.com.br",
  "department": "recursos humanos",
  "location": "manaus",
  "company_tenure": "entre 2 e 5 anos",
  "gender": "outro",
  "generation": "geração y",
  "l0_company": "empresa",
  "l1_directorate": "diretoria a",
  "l2_management": "gerência a1",
  "l3_coordination": "coordenação a11",
  "l4_area": "área a111",
  "response_date": "2022-01-20",
  "interest_in_position": 7,
  "interest_in_position_comments": "-",
  "contribution": 1,
  "contribution_comments": "-",
  "learning_and_development": 5,
  "learning_and_development_comments": "-",
  "feedback": 1,
  "feedback_comments": "-",
  "manager_interaction": 3,
  "manager_interaction_comments": "-",
  "opportunity_clarity": 4,
  "opportunity_clarity_comments": "-",
  "permanence_expectation": 7,
  "permanence_expectation_comments": "-",
  "enps": 8,
  "enps_comments": "A empresa incentiva a inovação e a criatividade."
}
```

**Resposta (exemplo):**
```json
{
  "data": {
    "id": "d39033df-88af-4d46-a3a4-a56776e17a66",
    "name": "Demo 019",
    "...": "..."
  },
  "meta": {}
}
```

---

### POST /api/v1/feedback/batch

Cria de **1 a 100 feedbacks** em uma única transação, com resposta na própria
requisição. Exige perfil `admin` e header `Idempotency-Key` válido.

O body é `{"items": [...]}`: cada objeto deve atender ao mesmo `FeedbackCreate`
do POST individual. Exemplo mínimo de um lote com um item:

```json
{
  "items": [
    {
      "name": "Pessoa A",
      "email": "pessoa.a@example.com",
      "corporate_email": "pessoa.a@company.com",
      "department": "Engenharia",
      "location": "São Paulo",
      "company_tenure": "1 ano",
      "gender": "Outro",
      "generation": "Geração Y",
      "interest_in_position": 7,
      "contribution": 7,
      "learning_and_development": 7,
      "feedback": 7,
      "manager_interaction": 7,
      "opportunity_clarity": 7,
      "permanence_expectation": 7,
      "enps": 8
    }
  ]
}
```

Salve em `batch.json` e envie:

```bash
curl -X POST http://127.0.0.1:8000/api/v1/feedback/batch \
  -H "Authorization: Bearer $TOKEN" \
  -H "Idempotency-Key: 59404415-383b-443d-9279-95a8fc15e306" \
  -H "Content-Type: application/json" --data-binary @batch.json
```

Resposta `200`, com IDs na ordem de entrada e índices começando em zero:

```json
{
  "data": [
    {"index": 0, "id": "d39033df-88af-4d46-a3a4-a56776e17a66"}
  ],
  "meta": {"created": 1}
}
```

- O lote inteiro é validado antes da gravação. Um item inválido retorna `422`,
  com posição e campo, por exemplo `body.items.2.email`; nenhum item é criado.
- Um erro durante qualquer inserção ou ao salvar a resposta desfaz **todo o lote**,
  incluindo a reserva da chave. Não há sucesso parcial.
- Mesma chave, usuário e lote retorna a resposta original por 24 horas. Alterar
  itens **ou sua ordem** com a mesma chave retorna `409`.
- A operação `feedback:batch-create:v1` possui espaço de chaves separado da
  criação individual. A mesma chave nos dois endpoints representa duas operações.
- O limite de espera por lock e o retorno `503`/`Retry-After` seguem a política
  de idempotência existente. Reenvie o lote inteiro com a mesma chave.
- A idempotência é do lote completo. Reenviar um subconjunto ou usar outra chave
  pode criar duplicatas. Itens iguais dentro do mesmo lote são criados separadamente.

Não há nova migration: o lote reutiliza a tabela da migration `0004`.
Os testes de integração também cobrem lotes concorrentes, ordem dos IDs, limite
máximo e rollback após uma falha no segundo item.

---

### GET /api/v1/feedback

Lista registros com **paginação** e **filtros**.

**Parâmetros de query (principais):**
- `page` (padrão: 1)
- `limit` (padrão: 10)
- `id`
- `name`, `email`, `corporate_email`, `department`, `location`, `gender`, `generation`  
  (filtros de texto via **substring**, case-insensitive)
- `response_date_from`, `response_date_to` (datas)
- Faixas numéricas:
  - `enps_min`, `enps_max`
  - `interest_in_position_min`, `interest_in_position_max`
  - `contribution_min`, `contribution_max`
  - `learning_and_development_min`, `learning_and_development_max`
  - `feedback_min`, `feedback_max`
  - `manager_interaction_min`, `manager_interaction_max`
  - `opportunity_clarity_min`, `opportunity_clarity_max`
  - `permanence_expectation_min`, `permanence_expectation_max`

**Exemplos:**
- Paginação:
  ```
  GET /api/v1/feedback?page=1&limit=20
  ```
- Texto + data:
  ```
  GET /api/v1/feedback?department=recursos&response_date_from=2024-01-01&response_date_to=2024-12-31
  ```
- Faixa de `enps`:
  ```
  GET /api/v1/feedback?enps_min=7&enps_max=10
  ```

**Resposta (exemplo):**
```json
{
  "data": [
    { "id": "d39033df-88af-4d46-a3a4-a56776e17a66", "name": "Demo 019", "...": "..." },
    { "id": "78245992-4564-4c71-b4b7-05ede27d341b", "name": "Demo 314", "...": "..." }
  ],
  "meta": { "page": 1, "limit": 5, "total": 12, "pages": 3 }
}
```

---

### PUT /api/v1/feedback/{id}

Substitui o registro completo. Envie todos os campos obrigatórios, usando o mesmo
body do POST. Campos anuláveis omitidos são definidos como `null`. Para uma
alteração parcial, use PATCH. O identificador deve ser um UUID válido.

Salve o exemplo completo do POST em `feedback.json` e execute:

```bash
curl -X PUT http://127.0.0.1:8000/api/v1/feedback/d39033df-88af-4d46-a3a4-a56776e17a66 \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" --data-binary @feedback.json
```

### PATCH /api/v1/feedback/{id}

Altera somente os campos enviados e retorna o registro completo atualizado.
Campos omitidos são preservados. Para limpar um comentário, telefone, nível
organizacional ou data, envie `null`. Campos obrigatórios não aceitam `null`.
Um objeto vazio, campos desconhecidos ou tentativa de alterar `id` retornam `422`.
Somente `admin` pode executar PATCH.

```bash
curl -X PATCH http://127.0.0.1:8000/api/v1/feedback/d39033df-88af-4d46-a3a4-a56776e17a66 \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"name":"Demo Atualizado","enps":9,"feedback_comments":null}'
```

PUT, PATCH e DELETE retornam `404` quando o registro não existe.
As respostas mantêm o envelope `{"data": ..., "meta": {}}`.

---

### DELETE /api/v1/feedback/{id}

Remove um registro pelo `id`.

**Resposta:**
```json
{ "data": { "id": "d39033df-88af-4d46-a3a4-a56776e17a66" }, "meta": {} }
```

---

## Paginação, filtros e ordenação

- **Paginação:** `page >= 1` e `1 <= limit <= 100` (padrões: 1 e 10).
- **Filtros:** conforme a lista do [GET /api/v1/feedback](#get-apiv1feedback).  
  Filtros de texto usam `ILIKE '%valor%'` no PostgreSQL.
- **Ordenação:** por padrão `response_date DESC NULLS LAST, id DESC`.

---

## Execução de testes

No diretório **`pin-api/`** (com **venv ativado**):

```bash
python -m unittest discover -s tests -v
```

Para preparar do zero:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt httpx
python -m unittest discover -s tests -v
```

> Os testes usam mocks assíncronos e `fastapi.testclient`, sem exigir banco de dados.

O acesso ao PostgreSQL usa Psycopg 3 com `AsyncConnectionPool`, aberto no lifespan do FastAPI e fechado no encerramento. Cada worker tem seu próprio pool (4 a 16 conexões). A inicialização aguarda conexões disponíveis e falha se o banco estiver indisponível. Cada operação usa uma conexão do pool, com commit em caso de sucesso e rollback em caso de erro. Configure a conexão pelas variáveis `DB_USER`, `DB_PASSWORD`, `DB_HOST`, `DB_PORT` e `DB_NAME`.


## Como executar o projeto?

Instale os requisitos

```
pip install -r requirements.txt
```

Dê permissão ao script que inicia o projeto

```
chmod +x start-docker-and-migrate.sh
```

Rode o arquivo .sh que iniciará o container docker da API e criará as tabelas no banco de dados

```
./start-docker-and-migrate.sh
```

## Como IA foi usada no projeto?

A IA foi usada em tarefas repetitivas com Copilot. Além de debug, criação do script .sh e enriquecimento do readme com ChatGPT.
## Testes de integração da idempotência

Os testes unitários não exigem PostgreSQL. Para executar também os testes de
concorrência e rollback, use **um banco descartável cujo nome comece com
`pin_test_`**, configure `DB_*` para ele e aplique as migrations antes:

```bash
# DB_* deve apontar exclusivamente para o banco descartável.
alembic upgrade head
PIN_API_INTEGRATION=1 python -m unittest tests.test_idempotency_integration -v
```

A suíte cria usuários e feedbacks de teste e os remove ao terminar. Não execute
contra um banco com dados reais. Os testes exercitam replay, conflitos, isolamento
por usuário, falha entre escritas, expiração concorrente, timeout e limpeza.
