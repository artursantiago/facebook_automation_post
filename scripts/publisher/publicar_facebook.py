import requests
import os
import json
import time
import random
import shutil
from datetime import datetime, timedelta

# =====================
# CONFIGURAÇÕES
# =====================
# INTERVALO_HORAS = 3
INTERVALO_HORAS = 0   
HORA_INICIO = 8
HORA_FIM = 23
# RANDOM_MINUTOS = 5
RANDOM_MINUTOS = 0
DRY_RUN = True  # ⚠️ MUDE PARA False QUANDO VALIDAR TUDO
SKIP_POSTING = False  # ⚠️ Se True, ignora todo o fluxo de publicação

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
TMP_DIR = os.path.join(BASE_DIR, "conteudo/tmp")
PUBLICADOS_DIR = os.path.join(BASE_DIR, "conteudo/publicados")
IMAGENS_DIR = os.path.join(BASE_DIR, "conteudo/imagens")
IMAGENS_PUBLICADAS_DIR = os.path.join(IMAGENS_DIR, "publicadas")
STATE_FILE = os.path.join(BASE_DIR, "state/facebook_posting.json")
FRASES_FILE = os.path.join(BASE_DIR, "conteudo/frases.json")
FRASES_USADAS_FILE = os.path.join(BASE_DIR, "conteudo/frases_usadas.json")
LOG_FILE = os.path.join(BASE_DIR, "publisher.log")
LOG_RETENTION_DAYS = 2

# =====================
# FACEBOOK API
# =====================
FACEBOOK_API_VERSION = "v24.0"
FACEBOOK_CREDENTIALS_FILE = os.path.join(BASE_DIR, "facebook_credentials.json")

# =====================
# UTILIDADES
# =====================
def log(msg):
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {msg}")


def carregar_estado():
    """
    Carrega o estado de publicação.

    Regras:
    - Se o arquivo NÃO existir → considera que nunca houve post
    - Se o arquivo estiver vazio → considera que nunca houve post
    - Se o arquivo for {} → considera que nunca houve post
    - Se faltar qualquer chave → normaliza automaticamente
    """

    estado_padrao = {
        "ultimo_post": None,
        "data": datetime.now().strftime("%Y-%m-%d")
    }

    # 1️⃣ Arquivo não existe
    if not os.path.exists(STATE_FILE):
        log("ℹ️ Estado inexistente — considerando primeiro post")
        return estado_padrao

    try:
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            conteudo = f.read().strip()

            # 2️⃣ Arquivo vazio
            if not conteudo:
                log("ℹ️ Estado vazio — considerando primeiro post")
                return estado_padrao

            estado = json.loads(conteudo)

            # 3️⃣ Arquivo contém apenas {}
            if not estado:
                log("ℹ️ Estado {} — considerando primeiro post")
                return estado_padrao

            # 4️⃣ Normalização defensiva
            if "ultimo_post" not in estado:
                estado["ultimo_post"] = None

            if "data" not in estado:
                estado["data"] = datetime.now().strftime("%Y-%m-%d")

            return estado

    except json.JSONDecodeError:
        log("⚠️ Estado corrompido — resetando estado")
        return estado_padrao


def salvar_estado(estado):
    os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(estado, f, indent=2, ensure_ascii=False)

def limpar_log_antigo():
    if not os.path.exists(LOG_FILE):
        return
    try:
        mtime = os.path.getmtime(LOG_FILE)
        idade = datetime.now() - datetime.fromtimestamp(mtime)
        if idade.days >= LOG_RETENTION_DAYS:
            open(LOG_FILE, "w").close()
            log("🧹 Log limpo (mais de 2 dias)")
    except Exception:
        pass


def horario_valido(estado):
    agora = datetime.now()

    if not (HORA_INICIO <= agora.hour <= HORA_FIM):
        return False

    if estado["ultimo_post"]:
        ultimo = datetime.fromisoformat(estado["ultimo_post"])
        intervalo = timedelta(hours=INTERVALO_HORAS)
        random_segundos = random.randint(0, RANDOM_MINUTOS * 60)
        random_delay = timedelta(seconds=random_segundos)
        if agora < ultimo + intervalo + random_delay:
            return False

    return True

# =====================
# FACEBOOK (GRAPH API)
# =====================
def carregar_credenciais_facebook():
    """
    Carrega Page ID e Page Access Token
    """
    if not os.path.exists(FACEBOOK_CREDENTIALS_FILE):
        raise FileNotFoundError("Arquivo facebook_credentials.json não encontrado")

    with open(FACEBOOK_CREDENTIALS_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)

    return data["page_id"], data["page_access_token"]   

def publicar_facebook(imagem_path, legenda):
    """
    Publica uma imagem com legenda na Página do Facebook usando Graph API
    """

    log("📤 Iniciando publicação no Facebook")

    if DRY_RUN:
        log("[DRY-RUN] Publicação simulada no Facebook")
        log(f"[DRY-RUN] Imagem: {imagem_path}")
        log(f"[DRY-RUN] Legenda: {legenda}")
        return True

    try:
        # =====================
        # 1️⃣ Carrega credenciais
        # =====================
        page_id, access_token = carregar_credenciais_facebook()
        log("🔑 Credenciais do Facebook carregadas")

        # =====================
        # 2️⃣ Monta endpoint
        # =====================
        url = f"https://graph.facebook.com/{FACEBOOK_API_VERSION}/{page_id}/photos"
        log(f"🌐 Endpoint: {url}")

        # =====================
        # 3️⃣ Prepara payload
        # =====================
        data = {
            "caption": legenda,
            "access_token": access_token
        }

        files = {
            "source": open(imagem_path, "rb")
        }

        # =====================
        # 4️⃣ Envia requisição
        # =====================
        response = requests.post(url, data=data, files=files)
        files["source"].close()

        # =====================
        # 5️⃣ Analisa resposta
        # =====================
        if response.status_code != 200:
            log("❌ Erro HTTP ao publicar no Facebook")
            log(f"Status: {response.status_code}")
            log(f"Resposta: {response.text}")
            return False

        resposta = response.json()

        if "id" not in resposta:
            log("❌ Facebook não retornou ID da publicação")
            log(str(resposta))
            return False

        log(f"✅ Publicado com sucesso no Facebook | Post ID: {resposta['id']}")
        return True

    except Exception as e:
        log(f"❌ Exceção ao publicar no Facebook: {e}")
        return False


# =====================
# WORKFLOW PRINCIPAL
# =====================
def main():
    limpar_log_antigo()

    if SKIP_POSTING:
        log("⚠️ SKIP_POSTING está habilitado - nenhuma ação será executada")
        return

    estado = carregar_estado()

    # Reset diário
    hoje = datetime.now().strftime("%Y-%m-%d")
    if estado["data"] != hoje:
        estado = {"ultimo_post": None, "data": hoje}

    if not horario_valido(estado):
        log("⏳ Fora do horário válido")
        return

    pacotes = sorted(os.listdir(TMP_DIR))
    if not pacotes:
        log("📂 Nenhuma imagem em tmp/")
        estado["ultimo_post"] = datetime.now().isoformat()
        salvar_estado(estado)
        return

    pacote = os.path.join(TMP_DIR, pacotes[0])

    imagem_editada = None
    frase_path = None

    for f in os.listdir(pacote):
        if "editada" in f:
            imagem_editada = os.path.join(pacote, f)
        elif f == "frase.json":
            frase_path = os.path.join(pacote, f)

    if not imagem_editada or not frase_path:
        log("❌ Pacote inválido, ignorando")
        return

    with open(frase_path, "r", encoding="utf-8") as f:
        frase_data = json.load(f)
        frase = frase_data["frase"]

    sucesso = publicar_facebook(imagem_editada, frase)

    if not sucesso:
        log("❌ Falha ao publicar no Facebook")
        return

    data_hoje = datetime.now().strftime("%Y-%m-%d")
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    # Nova estrutura: conteudo/publicados/[date]/[timestamp]/
    destino = os.path.join(PUBLICADOS_DIR, data_hoje, timestamp)
    os.makedirs(destino, exist_ok=True)

    # Garante que a pasta imagens/publicadas existe
    os.makedirs(IMAGENS_PUBLICADAS_DIR, exist_ok=True)

    for arquivo in os.listdir(pacote):
        origem = os.path.join(pacote, arquivo)
        if "imagem_original" in arquivo:
            # Move imagem original para conteudo/imagens/publicadas/[timestamp].[ext]
            extensao = os.path.splitext(arquivo)[1]
            novo_nome = f"{timestamp}{extensao}"
            shutil.move(origem, os.path.join(IMAGENS_PUBLICADAS_DIR, novo_nome))
        elif "editada" in arquivo:
            novo = f"imagem_publicada_{timestamp}.png"
            shutil.move(origem, os.path.join(destino, novo))
        elif arquivo == "frase.json":
            novo = f"frase_{timestamp}.json"
            shutil.move(origem, os.path.join(destino, novo))

    shutil.rmtree(pacote)

    # Remove a frase de frases.json
    if os.path.exists(FRASES_FILE):
        with open(FRASES_FILE, "r", encoding="utf-8") as f:
            frases = json.load(f)
        if frase in frases:
            frases.remove(frase)
            with open(FRASES_FILE, "w", encoding="utf-8") as f:
                json.dump(frases, f, ensure_ascii=False, indent=2)

    # Adiciona a frase em frases_usadas.json com formato "[timestamp]": "[frase]"
    frases_usadas = {}
    if os.path.exists(FRASES_USADAS_FILE):
        with open(FRASES_USADAS_FILE, "r", encoding="utf-8") as f:
            frases_usadas = json.load(f)
    frases_usadas[timestamp] = frase
    with open(FRASES_USADAS_FILE, "w", encoding="utf-8") as f:
        json.dump(frases_usadas, f, ensure_ascii=False, indent=2)

    estado["ultimo_post"] = datetime.now().isoformat()
    salvar_estado(estado)

    log("✅ Publicação concluída com sucesso")

if __name__ == "__main__":
    main()
