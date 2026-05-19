"""
Sistema de Impressão em Lote - Linea Brasil
Fase 1: Script local com interface web
"""

from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse
from pydantic import BaseModel
from pathlib import Path
import subprocess
import platform
import os
import socket
import tempfile
from typing import Optional
from datetime import datetime
from database import (
    registrar_log, gerar_codigo_rastreio, registrar_documento_impresso,
    listar_documentos, atualizar_status_documento, buscar_documento,
    atualizar_fase_documento, listar_logs, get_or_create_sistema_user,
)
import time
import logging
import argparse

# Certifique-se de que está exatamente assim, em linhas separadas ou bem limpo:
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ============================================
# FILTROS - AJUSTE CONFORME NECESSÁRIO
# ============================================

IGNORAR_PDFS = ["ENG - 011 - 510000000 - NOME PEÇA - P1-1 - V0",
                "ENG - 011 - 510000000 - NOME PEÇA - P1-1 - V1",
                "ENG - 011 - 510000000 - NOME PEÇA - P1-1 - V2"]

IGNORAR_PASTAS = ["- 003 -", "003 - MONTAGEM", "REVISAO", "REVISÃO"]

app = FastAPI(title="FastPrint - Linea Brasil")

# ============================================
# CONFIGURAÇÕES
# ============================================

# 1. Configuração do interpretador de argumentos
parser = argparse.ArgumentParser(description="Script de impressão automatizada.")

# Adiciona o argumento que você quer passar. 
# O 'default' define o que acontece se você NÃO passar o parâmetro.
parser.add_argument(
    "--ambiente", 
    type=str, 
    default="producao", 
    help="Define o ambiente de execução (teste ou producao)"
)

# 2. Faz o Python ler o que foi digitado no terminal
args = parser.parse_args()

# 3. Agora você pode usar a variável em um IF
if args.ambiente == "teste":
    SEARCH_PATHS = [r"C:\shared"]
else:    
    SEARCH_PATHS = [
        r"L:\Linea Brasil\6 Pesquisa e Desenvolvimento\1 - DOCUMENTOS\1 - DOCUMENTOS TECNICOS\1 - EM LINHA",
        r"L:\Linea Brasil\6 Pesquisa e Desenvolvimento\1 - DOCUMENTOS\1 - DOCUMENTOS TECNICOS\3 - EM REVISAO",
    ]


DEFAULT_PRINTER: Optional[str] = None

# ============================================
# MODELS
# ============================================

class PrintRequest(BaseModel):
    folder_path: str
    printer: Optional[str] = None
    selected_files: Optional[list[str]] = None
    fase: Optional[str] = None  # "Lote Teste", "Lote Piloto", "Lote Padrão"

class FolderRequest(BaseModel):
    path: str

class StatusUpdateRequest(BaseModel):
    codigo_rastreio: str
    novo_status: str  # "baixado"

class FaseUpdateRequest(BaseModel):
    codigo_rastreio: str
    fase: str  # "Lote Teste", "Lote Piloto", "Lote Padrão"
    por_produto: bool = False

# ============================================
# FUNÇÕES AUXILIARES
# ============================================

def get_hostname() -> str:
    try:
        return socket.gethostname()
    except:
        return "DESCONHECIDO"

def get_available_printers() -> list[str]:
    system = platform.system()

    if system == "Windows":
        try:
            result = subprocess.run(
                ["powershell", "-Command", "Get-Printer | Select-Object -ExpandProperty Name"],
                capture_output=True, text=True, timeout=10
            )
            if result.returncode == 0:
                return [p.strip() for p in result.stdout.strip().split('\n') if p.strip()]
        except Exception as e:
            print(f"Erro ao listar impressoras: {e}")

    return ["Impressora Padrão"]


def find_pdf_files(folder_path: str) -> list[dict]:
    path = Path(folder_path)

    if not path.exists():
        raise FileNotFoundError(f"Pasta não encontrada: {folder_path}")

    pdf_files = []

    def is_eng_folder(name: str) -> bool:
        upper_name = name.upper()
        return (upper_name.startswith("ENG -") or
                upper_name.startswith("ENG-") or
                upper_name == "ENG")

    def should_ignore_folder(name: str) -> bool:
        upper_name = name.upper()
        return any(termo in upper_name for termo in IGNORAR_PASTAS)

    def should_ignore_pdf(name: str) -> bool:
        upper_name = name.upper()
        return any(termo in upper_name for termo in IGNORAR_PDFS)

    def scan_folder(folder: Path, parent_name: str = ""):
        for item in folder.iterdir():
            if item.is_file() and item.suffix.lower() == ".pdf":
                if should_ignore_pdf(item.name):
                    continue
                display_folder = parent_name or folder.name
                pdf_files.append({
                    "name": item.name,
                    "path": str(item),
                    "folder": display_folder,
                    "size_kb": round(item.stat().st_size / 1024, 1)
                })
            elif item.is_dir() and not should_ignore_folder(item.name):
                scan_folder(item, parent_name or folder.name)

    for subdir in path.iterdir():
        if subdir.is_dir() and is_eng_folder(subdir.name) and not should_ignore_folder(subdir.name):
            scan_folder(subdir)

    if is_eng_folder(path.name):
        for item in path.iterdir():
            if item.is_file() and item.suffix.lower() == ".pdf":
                if not should_ignore_pdf(item.name):
                    pdf_files.append({
                        "name": item.name,
                        "path": str(item),
                        "folder": path.name,
                        "size_kb": round(item.stat().st_size / 1024, 1)
                    })

    return sorted(pdf_files, key=lambda x: (x["folder"], x["name"]))


def stamp_pdf(pdf_path: str, codigo_rastreio: str, fase: str = None, usuario: str = None) -> str | None:
    """
    Adiciona carimbo de rastreio no topo do PDF.
    Lê o tamanho e rotação reais de cada página para posicionar corretamente.
    Requer pypdf e reportlab instalados.
    """
    try:
        from pypdf import PdfReader, PdfWriter
        from reportlab.pdfgen import canvas
        import io

        reader = PdfReader(pdf_path)
        writer = PdfWriter()
        fase_parte    = f"  |  {fase}" if fase else ""
        usuario_parte = usuario or get_hostname()
        texto = f"FastPrint  |  {codigo_rastreio}{fase_parte}  |  {datetime.now().strftime('%d/%m/%Y %H:%M')}  |  {usuario_parte}"

        for page in reader.pages:
            # Lê dimensões reais da página
            w = float(page.mediabox.width)
            h = float(page.mediabox.height)

            # Lê rotação da página (0, 90, 180, 270)
            rotation = int(page.get("/Rotate") or 0)

            # Se a página tem rotação 90 ou 270, largura e altura são invertidas visualmente
            if rotation in (90, 270):
                w, h = h, w

            # Cria carimbo com o tamanho exato desta página
            packet = io.BytesIO()
            c = canvas.Canvas(packet, pagesize=(w, h))

            c.setStrokeColorRGB(0.75, 0.75, 0.75)
            c.setLineWidth(0.4)
            c.line(20, h - 18, w - 20, h - 18)

            c.saveState()
            c.setFont("Helvetica", 7)
            c.setFillColorRGB(0.5, 0.5, 0.5)
            c.translate(20, h - 13)
            c.drawString(0, 0, texto)
            c.restoreState()

            c.save()
            packet.seek(0)

            stamp_page = PdfReader(packet).pages[0]

            # Se a página tem rotação, precisamos aplicar o carimbo antes de rotacionar
            # para o merge ficar no sistema de coordenadas correto
            if rotation != 0:
                # Remove a rotação temporariamente, faz o merge, reaplica
                page["/Rotate"] = 0
                # Recria o carimbo sem inverter w/h (coordenadas internas reais)
                w_real = float(page.mediabox.width)
                h_real = float(page.mediabox.height)
                packet2 = io.BytesIO()
                c2 = canvas.Canvas(packet2, pagesize=(w_real, h_real))

                if rotation == 90:
                    # Topo visual = lado direito interno
                    c2.setStrokeColorRGB(0.75, 0.75, 0.75)
                    c2.setLineWidth(0.4)
                    c2.line(w_real - 18, 20, w_real - 18, h_real - 20)
                    c2.saveState()
                    c2.setFont("Helvetica", 7)
                    c2.setFillColorRGB(0.5, 0.5, 0.5)
                    c2.translate(w_real - 13, h_real - 20)
                    c2.rotate(270)
                    c2.drawString(0, 0, texto)
                    c2.restoreState()
                elif rotation == 270:
                    # Topo visual = lado esquerdo interno
                    c2.setStrokeColorRGB(0.75, 0.75, 0.75)
                    c2.setLineWidth(0.4)
                    c2.line(18, 20, 18, h_real - 20)
                    c2.saveState()
                    c2.setFont("Helvetica", 7)
                    c2.setFillColorRGB(0.5, 0.5, 0.5)
                    c2.translate(13, 20)
                    c2.rotate(90)
                    c2.drawString(0, 0, texto)
                    c2.restoreState()
                elif rotation == 180:
                    # Topo visual = rodapé interno
                    c2.setStrokeColorRGB(0.75, 0.75, 0.75)
                    c2.setLineWidth(0.4)
                    c2.line(20, 18, w_real - 20, 18)
                    c2.saveState()
                    c2.setFont("Helvetica", 7)
                    c2.setFillColorRGB(0.5, 0.5, 0.5)
                    c2.translate(20, 13)
                    c2.drawString(0, 0, texto)
                    c2.restoreState()

                c2.save()
                packet2.seek(0)
                stamp_page = PdfReader(packet2).pages[0]
                page.merge_page(stamp_page)
                page["/Rotate"] = rotation  # reaplica a rotação original
            else:
                page.merge_page(stamp_page)

            writer.add_page(page)

        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf", prefix=f"fp_{codigo_rastreio}_")
        with open(tmp.name, "wb") as f:
            writer.write(f)

        return tmp.name

    except ImportError:
        print("AVISO: pypdf ou reportlab não instalado. Imprimindo sem carimbo.")
        return None
    except Exception as e:
        print(f"Erro ao carimbar PDF: {e}")
        return None


def print_pdf(pdf_path: str, printer: Optional[str] = None) -> dict:

    start_time = time.perf_counter()  # Marca o início da execução
    logger.info(f"Iniciando processo de impressão: {pdf_path}")

    if not Path(pdf_path).exists():
        logger.error(f"Arquivo não encontrado no caminho especificado: {pdf_path}")
        return {"success": False, "error": f"Arquivo não encontrado: {pdf_path}"}

    # Busca pelo executável
    search_start = time.perf_counter()
    sumatra_paths = [
        os.path.expandvars(r"%LOCALAPPDATA%\SumatraPDF\SumatraPDF.exe"),
        r"C:\Users\{}\AppData\Local\SumatraPDF\SumatraPDF.exe".format(os.environ.get('USERNAME', '')),
        r"C:\Program Files\SumatraPDF\SumatraPDF.exe",
        r"C:\Program Files (x86)\SumatraPDF\SumatraPDF.exe",
        "SumatraPDF.exe",
    ]

    sumatra_exe = None
    for path in sumatra_paths:
        if Path(path).exists():
            sumatra_exe = path
            break

    if not sumatra_exe:
        try:
            result = subprocess.run(["where", "SumatraPDF.exe"], capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                sumatra_exe = result.stdout.strip().split('\n')[0]
        except Exception as e:
            logger.warning(f"Erro ao tentar localizar Sumatra via 'where': {e}")

    search_duration = time.perf_counter() - search_start
    logger.debug(f"Busca pelo executável levou: {search_duration:.4f}s")

    if not sumatra_exe:
        logger.error("Executável SumatraPDF não foi localizado no sistema.")
        return {"success": False, "error": "SumatraPDF não encontrado."}

    # Comando de impressão
    try:
        if printer:
            cmd = [sumatra_exe, "-print-to", printer, "-silent", pdf_path]
            logger.info(f"Enviando para impressora específica: {printer}")
        else:
            cmd = [sumatra_exe, "-print-to-default", "-silent", pdf_path]
            logger.info("Enviando para impressora padrão.")

        process_start = time.perf_counter()
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        process_duration = time.perf_counter() - process_start

        total_duration = time.perf_counter() - start_time

        if result.returncode == 0:
            logger.info(f"Sucesso! Tempo do subprocesso: {process_duration:.2f}s | Tempo total: {total_duration:.2f}s")
            return {"success": True, "message": f"Enviado para impressão: {Path(pdf_path).name}"}
        else:
            error_msg = result.stderr or result.stdout or "Erro desconhecido"
            logger.error(f"Erro no SumatraPDF (Code {result.returncode}): {error_msg}")
            return {"success": False, "error": error_msg}

    except subprocess.TimeoutExpired:
        logger.error(f"Timeout após 60 segundos na tentativa de impressão.")
        return {"success": False, "error": "Timeout - impressão demorou demais"}
    except Exception as e:
        logger.exception(f"Erro inesperado durante a execução: {e}")
        return {"success": False, "error": str(e)}

# ============================================
# ROTAS DA API
# ============================================

@app.get("/api/logs")
async def get_logs(limite: int = 100):
    return {"logs": listar_logs(limite)}

# --- RASTREIO ---

@app.get("/api/documentos")
async def get_documentos(status: str = None, limite: int = 200):
    docs = listar_documentos(status=status, limite=limite)
    return {"documentos": docs, "total": len(docs)}

@app.post("/api/documentos/status")
async def update_status(request: StatusUpdateRequest):
    usuario_id = get_or_create_sistema_user()
    ok = atualizar_status_documento(request.codigo_rastreio, request.novo_status, usuario_id)
    if not ok:
        raise HTTPException(status_code=400, detail="Documento não encontrado ou status inválido para esta transição")
    doc = buscar_documento(request.codigo_rastreio)
    return {"success": True, "documento": doc}

@app.post("/api/documentos/fase")
async def update_fase(request: FaseUpdateRequest):
    fases_validas = ["Lote Teste", "Lote Piloto", "Lote Padrão"]
    if request.fase not in fases_validas:
        raise HTTPException(status_code=400, detail="Fase inválida")
    affected = atualizar_fase_documento(request.codigo_rastreio, request.fase, request.por_produto)
    if affected == 0:
        raise HTTPException(status_code=404, detail="Documento não encontrado")
    return {"success": True, "affected": affected}

@app.get("/api/documentos/{codigo}")
async def get_documento(codigo: str):
    doc = buscar_documento(codigo)
    if not doc:
        raise HTTPException(status_code=404, detail="Documento não encontrado")
    return doc

# --- IMPRESSÃO ---

@app.get("/", response_class=HTMLResponse)
async def root():
    return FileResponse("static/index.html")

@app.get("/api/printers")
async def list_printers():
    printers = get_available_printers()
    return {"printers": printers, "default": DEFAULT_PRINTER}

@app.post("/api/list-pdfs")
async def list_pdfs(request: FolderRequest):
    try:
        pdfs = find_pdf_files(request.path)
        return {"success": True, "folder": request.path, "total": len(pdfs), "files": pdfs}
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/print")
async def print_files(request: PrintRequest):
    """Imprime PDFs selecionados — com carimbo de rastreio e registro no banco"""
    try:
        if request.selected_files:
            pdfs = [{"path": f, "name": Path(f).name} for f in request.selected_files]
        else:
            pdfs = find_pdf_files(request.folder_path)

        if not pdfs:
            return {"success": False, "message": "Nenhum PDF para imprimir"}

        usuario_id   = get_or_create_sistema_user()
        computador   = get_hostname()
        produto      = Path(request.folder_path).name

        results = []
        success_count = 0
        codigos_gerados = []
        arquivos_tmp = []

        for pdf in pdfs:
            codigo = gerar_codigo_rastreio(computador)

            pdf_para_imprimir = stamp_pdf(pdf["path"], codigo, request.fase, computador)
            usou_tmp = pdf_para_imprimir is not None

            if not usou_tmp:
                pdf_para_imprimir = pdf["path"]
            else:
                arquivos_tmp.append(pdf_para_imprimir)

            result = print_pdf(pdf_para_imprimir, request.printer)
            result["codigo_rastreio"] = codigo
            results.append({"file": pdf["name"], **result})

            if result["success"]:
                success_count += 1
                codigos_gerados.append(codigo)
                registrar_documento_impresso(
                    codigo_rastreio=codigo,
                    produto=produto,
                    arquivo=pdf["name"],
                    pasta=request.folder_path,
                    impressora=request.printer or "Padrão",
                    computador=computador,
                    usuario_id=usuario_id,
                    fase=request.fase
                )

        for tmp in arquivos_tmp:
            try:
                os.unlink(tmp)
            except:
                pass

        try:
            arquivos_ok = [r["file"] for r in results if r.get("success")]
            registrar_log(
                usuario_id=usuario_id,
                produto=produto,
                pasta=request.folder_path,
                arquivos=arquivos_ok,
                impressora=request.printer or "Padrão"
            )
        except:
            pass

        return {
            "success": success_count > 0,
            "total": len(pdfs),
            "printed": success_count,
            "failed": len(pdfs) - success_count,
            "results": results,
            "codigos_rastreio": codigos_gerados
        }

    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/search")
async def search_products(query: str = ""):
    if not query or len(query) < 3:
        return {"success": False, "message": "Digite pelo menos 3 caracteres", "results": []}

    results = []

    for search_path in SEARCH_PATHS:
        status_path = Path(search_path)
        if not status_path.exists():
            continue

        status_name = status_path.name.split(" - ")[1] if " - " in status_path.name else status_path.name

        for item in status_path.iterdir():
            if not item.is_dir():
                continue

            is_product = item.name[:9].isdigit() and len(item.name) >= 9

            if is_product:
                if query.upper() in item.name.upper():
                    pdf_count = sum(1 for sub in item.iterdir()
                                   if sub.is_dir() and sub.name.upper().startswith("ENG")
                                   for p in sub.rglob("*.pdf") if not any(termo in str(p).upper() for termo in IGNORAR_PASTAS))
                    results.append({
                        "name": item.name, "path": str(item),
                        "type": "PRODUTO", "status": status_name, "pdf_count": pdf_count
                    })
            else:
                for product_folder in item.iterdir():
                    if not product_folder.is_dir():
                        continue
                    if query.upper() in product_folder.name.upper():
                        pdf_count = sum(1 for sub in product_folder.iterdir()
                                       if sub.is_dir() and sub.name.upper().startswith("ENG")
                                       for p in sub.rglob("*.pdf") if not any(termo in str(p).upper() for termo in IGNORAR_PASTAS))
                        results.append({
                            "name": product_folder.name, "path": str(product_folder),
                            "type": "PRODUTO", "status": status_name, "pdf_count": pdf_count
                        })

    results.sort(key=lambda x: (x["status"], x["name"]))
    return {"success": True, "query": query, "total": len(results), "results": results[:20]}


@app.get("/api/browse")
async def browse_folder(path: str = ""):
    try:
        if not path:
            path = SEARCH_PATHS[0]

        folder = Path(path)

        if not folder.exists():
            raise HTTPException(status_code=404, detail="Pasta não encontrada")

        items = []
        for item in sorted(folder.iterdir()):
            if item.is_dir():
                pdf_count = 0
                for subdir in item.iterdir():
                    if subdir.is_dir() and subdir.name.upper().startswith("ENG"):
                        pdf_count += len(list(subdir.glob("*.pdf")))
                items.append({
                    "name": item.name, "path": str(item),
                    "is_dir": True, "pdf_count": pdf_count
                })

        return {"current": str(folder), "parent": str(folder.parent) if folder.parent != folder else None, "items": items}

    except PermissionError:
        raise HTTPException(status_code=403, detail="Sem permissão para acessar esta pasta")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


app.mount("/static", StaticFiles(directory="static"), name="static")


if __name__ == "__main__":
    import uvicorn
    print("\n" + "="*50)
    print("FastPrint - Linea Brasil")
    print("="*50)
    print(f"Acesse: http://localhost:8080")
    print(f"\nPara a equipe acessar, use seu IP local:")
    print(f"   http://SEU_IP:8080")
    print("\n" + "="*50 + "\n")

    uvicorn.run(app, host="0.0.0.0", port=8080)
