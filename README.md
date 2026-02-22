## cloudNein (web app)

cloudNein is a privacy-first chat interface: **keeping what matters local**. Sensitive entities (company names, people) are detected on-device with Cactus. When entities are present and a secret key is set, their values are **encrypted** and only the encrypted sentence is sent to a **server farm** container; the server decrypts, enriches from a local knowledge base (e.g. Nvidia revenue 2025), and calls Gemini. Otherwise, redacted context is sent to Gemini or the local model answers.

**Run the app:**

1. **Environment** (repo root): copy or create `.env` with:
   ```bash
   CLOUDNEIN_SECRET_KEY=<base64-fernet-key>
   GEMINI_API_KEY=<your-gemini-key>
   ```
   Generate a Fernet key: `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`.

2. **Server farm** (decrypts + Gemini + knowledge base). Either:
   - **Docker:** `docker compose up --build -d` (exposes port 8001), or
   - **Direct:** from repo root, `pip install -r server/requirements.txt` then:
     ```bash
     source venv/bin/activate
     export $(grep -v '^#' .env | xargs)   # load .env
     uvicorn server.main:app --host 0.0.0.0 --port 8001
     ```

3. **Backend API** (from repo root):
   ```bash
   pip install -r api/requirements.txt
   uvicorn api.main:app --reload
   ```
   The API reads `.env` and calls the server farm at `http://localhost:8001` by default; set `SERVER_FARM_URL` if the server runs elsewhere.

4. **Frontend:**
   ```bash
   cd web && npm install && npm run dev
   ```

5. Open [http://localhost:5173](http://localhost:5173) for the landing page, or [http://localhost:5173/chat](http://localhost:5173/chat) to chat. The UI talks to the API at `http://localhost:8000` by default; set `VITE_API_URL` if the API runs elsewhere.

**Flow:** User message → Cactus extracts entities → if entities + `CLOUDNEIN_SECRET_KEY`: encrypt entity values, send encrypted sentence + key to server farm → server decrypts, looks up knowledge base (e.g. Nvidia revenue 2025 = $25,000M), calls Gemini → response shown in chat with source **server farm**. Otherwise, local reply or redacted Gemini fallback.

### Why specific tools (e.g. `lookup_company_data`) beat a generic “sensitive data” tool

Because of **training data and capacity limits**, small language models (SLMs) are much less reliable on broad, abstract tasks. A single tool like `lookup_sensitive_data` (“find any sensitive information”) is vague and hard for the SLM to map to concrete behaviour, so tool-call accuracy drops. **Narrow, task-specific tools** that match how the model was trained—e.g. “look up data for **this company**” or “look up info for **this person**”—give a clear, concrete target and **drastically improve reliability**.

Example: we use concrete tools like `lookup_company_data`, `lookup_person`, and `general_query` instead of one abstract “sensitive data” tool. Keep the **number of tools small (e.g. 3–4)** so the SLM is not overwhelmed; too many tools hurt tool accuracy.

### Mobile version

The React Native (iOS/Android) app lives in a separate repo: **[CactusHackApp](https://github.com/theianmay/CactusHackApp)**. It uses the Ignite boilerplate; see that repo for setup (`npm install --legacy-peer-deps`, `npm run start`) and build commands (`npm run build:ios:sim`, etc.).

---

## Cactus / Hackathon reference

- **Cactus** runs FunctionGemma on-device (Macs, mobile, wearables) and supports hybrid edge/cloud (e.g. Gemini) strategies. You need a Mac for local dev; get a key from [cactuscompute.com](https://cactuscompute.com/dashboard/api-keys) and run `cactus auth`.
- **Setup:** Clone [cactus](https://github.com/cactus-compute/cactus), run `./setup`, `cactus build --python`, `cactus download google/functiongemma-270m-it --reconvert`. Set `GEMINI_API_KEY`; claim credits by location ([SF](https://trygcp.dev/claim/cactus-x-gdm-hackathon-sf), [Boston](https://trygcp.dev/claim/cactus-x-gdm-hackathon-boston), [DC](https://trygcp.dev/claim/cactus-x-gdm-hackathon-dc), [London](https://trygcp.dev/claim/cactus-x-gdm-hackathon-london), [Singapore](https://trygcp.dev/claim/cactus-x-gdm-hackathon), [Online](https://trygcp.dev/claim/cactus-x-gdm-hackathon-online)).
- **Challenge:** Modify `generate_hybrid` in `main.py` (keep its signature); rank by tool-call correctness, speed, edge/cloud ratio. Submit: `python submit.py --team "YourTeamName" --location "YourCity"` (max 1x/hr). [Leaderboard](https://cactusevals.ngrok.app). Judging: hybrid routing quality, end-to-end products, voice-to-action with `cactus_transcribe`.
- **API:** Use `cactus_init`, `cactus_complete` (with `tools`, `confidence_threshold`, streaming `callback`), `cactus_transcribe`, `cactus_embed`, `cactus_rag_query`, `cactus_reset` / `cactus_stop` / `cactus_destroy`. See the Cactus repo and [Reddit r/cactuscompute](https://www.reddit.com/r/cactuscompute/) for full reference and help. 
