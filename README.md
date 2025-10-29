# Pin-api

Essa API faz operações CRUD em um banco de dados Postgres. Abaixo, vamos entender cada endpoint.

## Requisitos
- Python
- Docker

## Endpoints

### POST /api/v1/feedback

Cria um registro na tabela `employee_feedback`.

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
    "id": 42,
    "name": "Demo 019",
    "...": "..."
  },
  "meta": {}
}
```

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
    { "id": 1, "name": "Demo 019", "...": "..." },
    { "id": 2, "name": "Demo 314", "...": "..." }
  ],
  "meta": { "page": 1, "limit": 5, "total": 12, "pages": 3 }
}
```

---

### PUT /api/v1/feedback/{id}

Atualiza um registro existente.

**Curl:**
```bash
curl -X PUT http://127.0.0.1:8000/api/v1/feedback/42   -H "Content-Type: application/json"   -d '{"name":"Demo Atualizado","enps":9}'
```

**Resposta:**
```json
{
  "data": {
    "id": "42",
    "name": "Demo Atualizado",
    "enps": 9,
    "...": "..."
  },
  "meta": {}
}
```

---

### DELETE /api/v1/feedback/{id}

Remove um registro pelo `id`.

**Resposta:**
```json
{ "data": { "id": "42" }, "meta": {} }
```

---

## Paginação, filtros e ordenação

- **Paginação:** `page` e `limit` (padrões: 1 e 10).
- **Filtros:** conforme a lista do [GET /api/v1/feedback](#get-apiv1feedback).  
  Filtros de texto usam `ILIKE '%valor%'` no PostgreSQL.
- **Ordenação:** por padrão `response_date DESC NULLS LAST`.

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
python -m pip install fastapi "pydantic>=2" uvicorn httpx psycopg2cffi
python -m unittest discover -s tests -v
```

> Os testes usam um **stub** de `psycopg2cffi` para evitar dependência real de banco e `fastapi.testclient` para testar endpoints.


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