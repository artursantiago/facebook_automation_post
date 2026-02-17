import json
import shutil
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageFilter

# =========================
# CONFIGURAÇÕES DE CAMINHO
# =========================

# Sobe 3 níveis: gerador/ -> scripts/ -> automacao/
PROJETO_DIR = Path(__file__).resolve().parent.parent.parent
BASE_DIR = PROJETO_DIR / "conteudo"

IMAGENS_DIR = BASE_DIR / "imagens"
TMP_DIR = BASE_DIR / "tmp"
FRASES_PATH = BASE_DIR / "frases.json"

# =========================
# CONFIGURAÇÕES DE TEXTO
# =========================

TEXTO_Y = 350
FONTE_TAMANHO = 60
LARGURA_MAX_TEXTO_PERCENT = 0.9
FONTE_PATH = "/System/Library/Fonts/Supplemental/Comic Sans MS.ttf"

# =========================
# FUNÇÕES DE CONTROLE
# =========================

def listar_imagens_disponiveis():
    return [
        img for img in sorted(IMAGENS_DIR.iterdir())
        if img.is_file()
        and img.suffix.lower() in (".jpg", ".jpeg", ".png")
    ]


def listar_frases_disponiveis():
    if not FRASES_PATH.exists():
        return []
    with open(FRASES_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def criar_pasta_tmp():
    TMP_DIR.mkdir(exist_ok=True)
    existentes = [
        int(p.name) for p in TMP_DIR.iterdir()
        if p.is_dir() and p.name.isdigit()
    ]
    proximo = max(existentes, default=0) + 1

    pasta = TMP_DIR / str(proximo)
    pasta.mkdir()
    return pasta

# =========================
# TEXTO
# =========================

def quebrar_texto_para_largura(draw, texto, fonte, largura_max):
    linhas_finais = []

    for bloco in texto.split("\n"):
        palavras = bloco.split(" ")
        linha_atual = ""

        for palavra in palavras:
            teste = linha_atual + palavra + " "
            bbox = draw.textbbox((0, 0), teste, font=fonte)
            largura = bbox[2] - bbox[0]

            if largura <= largura_max:
                linha_atual = teste
            else:
                linhas_finais.append(linha_atual.rstrip())
                linha_atual = palavra + " "

        if linha_atual:
            linhas_finais.append(linha_atual.rstrip())

    return "\n".join(linhas_finais)

# =========================
# EFEITO LIFT
# =========================

def draw_text_lift(
    base_image,
    position,
    text,
    font,
    fill=(255, 255, 255, 255),
    shadow_color=(0, 0, 0, 160),
    offset=(0, 6),
    blur_radius=10,
    align="center",
    spacing=10
):
    shadow_layer = Image.new("RGBA", base_image.size, (0, 0, 0, 0))
    shadow_draw = ImageDraw.Draw(shadow_layer)

    x, y = position
    ox, oy = offset

    shadow_draw.multiline_text(
        (x + ox, y + oy),
        text,
        font=font,
        fill=shadow_color,
        align=align,
        spacing=spacing
    )

    shadow_layer = shadow_layer.filter(
        ImageFilter.GaussianBlur(blur_radius)
    )

    base_image.alpha_composite(shadow_layer)

    draw = ImageDraw.Draw(base_image)
    draw.multiline_text(
        (x, y),
        text,
        font=font,
        fill=fill,
        align=align,
        spacing=spacing
    )

# =========================
# PROCESSAMENTO DE IMAGEM
# =========================

def gerar_imagem_editada(imagem_path: Path, frase: str):
    # Processa a imagem em memória primeiro (sem criar pasta tmp)
    imagem = Image.open(imagem_path).convert("RGBA")
    draw = ImageDraw.Draw(imagem)

    largura_img, _ = imagem.size
    largura_max_texto = largura_img * LARGURA_MAX_TEXTO_PERCENT

    fonte = ImageFont.truetype(FONTE_PATH, FONTE_TAMANHO)

    texto_formatado = quebrar_texto_para_largura(
        draw, frase, fonte, largura_max_texto
    )

    bbox = draw.multiline_textbbox(
        (0, 0),
        texto_formatado,
        font=fonte,
        align="center",
        spacing=10
    )

    largura_texto = bbox[2] - bbox[0]
    pos_x = (largura_img - largura_texto) / 2

    draw_text_lift(
        imagem,
        (pos_x, TEXTO_Y),
        texto_formatado,
        font=fonte,
        fill=(255, 255, 255, 255),
        shadow_color=(0, 0, 0, 160),
        offset=(0, 6),
        blur_radius=10,
        align="center",
        spacing=10
    )

    # Se chegou aqui, a edição foi bem sucedida - agora cria a pasta tmp
    pasta_tmp = criar_pasta_tmp()

    # Salva a imagem editada
    imagem.save(pasta_tmp / "imagem_editada.png")

    # Move a imagem original para a pasta tmp (renomeando para imagem_original.[ext])
    extensao = imagem_path.suffix
    imagem_original_destino = pasta_tmp / f"imagem_original{extensao}"
    shutil.move(str(imagem_path), str(imagem_original_destino))

    # Salva a frase como JSON
    with open(pasta_tmp / "frase.json", "w", encoding="utf-8") as f:
        json.dump({"frase": frase}, f, ensure_ascii=False, indent=2)

    return pasta_tmp

# =========================
# WORKFLOW PRINCIPAL
# =========================

def processar_lote():
    imagens = listar_imagens_disponiveis()
    frases = listar_frases_disponiveis()

    if not imagens:
        print("Nenhuma imagem disponível.")
        return

    if not frases:
        print("Nenhuma frase disponível.")
        return

    total_processado = 0

    for imagem, frase in zip(imagens, frases):
        try:
            pasta = gerar_imagem_editada(imagem, frase)
            print(f"✔ Gerado com sucesso: {pasta}")
            total_processado += 1

        except Exception as e:
            print(f"❌ Erro ao processar {imagem.name}: {e}")

    print(f"\nProcessamento concluído. Total gerado: {total_processado}")

# =========================
# ENTRYPOINT
# =========================

if __name__ == "__main__":
    processar_lote()
