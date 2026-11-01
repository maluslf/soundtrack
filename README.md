# SoundRack

Uma arara de roupas virtual onde cada peça tem a sua trilha sonora (streetwear · trap · rock).
Backend em **FastAPI + SQLite (SQL puro)**, integração com **Spotify**, frontend em **HTML5 + Tailwind (CDN) + JavaScript puro**.

## Estrutura de pastas

```
soundrack/
├── main.py              # app FastAPI: rotas /api/*, StaticFiles, serve o index
├── db.py                # SQLite com SQL puro + CLI (python db.py --reset)
├── spotify.py           # Spotify (Client Credentials) + fallback iTunes, com cache
├── schema.sql           # CREATE TABLE + INSERTs (items, tracks, item_tracks)
├── requirements.txt
├── .env.example         # modelo das credenciais
├── .gitignore
├── assets/
│   └── clothes/         # as 16 imagens (nomes exatos, com espaços e "ç")
└── static/
    ├── index.html
    └── script.js
```

## Como executar

Requer Python 3.10+.

1. **Entre na pasta do projeto** (a que contém `main.py` e `assets/`).
2. **Crie o ambiente virtual e instale as dependências**
   ```bash
   python -m venv .venv
   source .venv/bin/activate          # Windows: .venv\Scripts\activate
   pip install -r requirements.txt
   ```
3. **Configure o Spotify** (ver abaixo) copiando o modelo:
   ```bash
   cp .env.example .env               # Windows: copy .env.example .env
   ```
   e preencha `SPOTIFY_CLIENT_ID` e `SPOTIFY_CLIENT_SECRET` no `.env`.
4. **Arranque o servidor**
   ```bash
   uvicorn main:app --reload
   ```
   A base `soundrack.db` é criada e povoada sozinha a partir do `schema.sql` na primeira execução.
5. Abra **http://127.0.0.1:8000**. A documentação automática da API está em `/docs`.

### Credenciais do Spotify

1. Entre em <https://developer.spotify.com/dashboard> e clique em **Create app**.
2. Dê um nome, uma descrição e, em *Redirect URI*, use `http://127.0.0.1:8000/callback` (o app não usa login de utilizador, mas o formulário exige um valor). Marque **Web API**.
3. Abra **Settings** da app e copie o **Client ID** e o **Client secret** para o `.env`.
4. Reinicie o servidor. Confirme em `http://127.0.0.1:8000/api/health` que `spotify_configured` está `true`.

As credenciais só são lidas de variáveis de ambiente (ou do `.env`, que está no `.gitignore`).

### Sobre as prévias de áudio

O Spotify deixou de devolver `preview_url` para muitas apps criadas depois de novembro de 2024. Por isso, quando o Spotify não traz preview, o `spotify.py` busca a prévia de 30 s na **iTunes Search API** (sem chave). A capa continua a vir do Spotify sempre que possível. Para desligar o fallback: `ITUNES_FALLBACK=false`.

Se o Spotify falhar (credenciais inválidas, rate limit, rede), a API **não dá erro**: devolve a peça com `cover_url`, `preview_url` e `spotify_url` a `null`, e o painel mostra um aviso.

## Endpoints

| Rota | Descrição |
|---|---|
| `GET /api/items` | Lista as 16 peças (com `?style=Trap` opcional). Leve: não consulta o Spotify. |
| `GET /api/items/{id}` | Peça + faixas com `cover_url`, `preview_url`, `spotify_url` resolvidos. |
| `GET /api/styles` | Estilos e contagem de peças. |
| `GET /api/health` | Estado da integração com o Spotify. |

## Notas importantes

- **Extensões das imagens:** `schema.sql` guarda o nome *sem extensão* (`calça 1`). O backend lê `assets/clothes/` e descobre a extensão real (`.png`, `.jpg`, `.webp`…), comparando em Unicode NFC (o macOS grava `ç` decomposto). O frontend monta o URL com `encodeURIComponent`. Se faltar alguma imagem, o servidor avisa no arranque e a arara mostra um marcador.
- **Metadados inferidos:** marca, estilo e detalhes foram deduzidos dos *nomes dos ficheiros* (não vi as imagens). Só `puffer_travis` (Cactus Jack), `marty supreme black jacket` e `t shirt fight club` têm marca inferida; as restantes usam "SoundRack Archive". Edite o `schema.sql` à vontade e rode `python db.py --reset`.
- **Faixas:** os títulos/artistas estão no `schema.sql`. Se uma faixa não for encontrada, o app tenta uma busca mais aberta; para o artista **2ZDinizz** a busca usa a faixa mais popular do artista. Para fixar uma faixa exata, preencha `tracks.spotify_id`.
- **Atalhos:** arrastar ou rolar a arara, setas do teclado entre peças, `Enter` seleciona, `Esc` fecha o painel.
