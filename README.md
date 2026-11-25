# Pin-api

Essa API faz operações CRUD em um banco de dados Postgres. Abaixo, vamos entender cada endpoint.

## Requisitos
- Python
- Docker

## Autenticação e autorização

A demonstração representa uma única organização e deve usar apenas dados fictícios.
Todos os endpoints `/api/v1/feedback` exigem `Authorization: Bearer <token>`.

| Perfil | GET | POST / PUT / DELETE |
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