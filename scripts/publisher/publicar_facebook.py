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
# UTILIDADES
# =====================
def log(msg):
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {msg}")


def carregar_estado():
    # Se o arquivo não existe, retorna estado inicial
    if not os.path.exists(STATE_FILE):
        return {
            "ultimo_post": None,
            "data": datetime.now().strftime("%Y-%m-%d")
        }
    # Se o arquivo existe mas está vazio ou corrompido
    try:
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            conteudo = f.read().strip()
            if not conteudo:  # vazio
                return {
                    "ultimo_post": None,
                    "data": datetime.now().strftime("%Y-%m-%d")
                }
            return json.loads(conteudo)
    except json.JSONDecodeError:
        # caso corrompido
        return {
            "ultimo_post": None,
            "data": datetime.now().strftime("%Y-%m-%d")
        }


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
# FACEBOOK (PLACEHOLDER)
# =====================
def publicar_facebook(imagem_path, legenda):
    if DRY_RUN:
        log("[DRY-RUN] Publicação simulada no Facebook")
        log(f"[DRY-RUN] Imagem: {imagem_path}")
        log(f"[DRY-RUN] Legenda: {legenda}")
        return True

    # ⚠️ AQUI entra a chamada real ao Facebook Graph API
    # retorno True SOMENTE se a API confirmar sucesso
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
