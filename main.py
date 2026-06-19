"""
Sistema de Impressão em Lote - FastPrint - Linea Brasil
Fase 1: Script local com interface web

Este módulo é o ponto de entrada da aplicação. Ele configura o servidor FastAPI,
define as rotas da API REST e contém as funções auxiliares para:
  - Busca de produtos em pastas compartilhadas na rede
  - Listagem e filtragem de arquivos PDF nas pastas de engenharia (ENG)
  - Envio de PDFs para impressão via CUPS com carimbo de rastreio
  - Registro de documentos impressos e rastreio de status
"""

from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse
from pydantic import BaseModel
from pathlib import Path
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

# Configuração do sistema de logging para rastrear operações do servidor
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ============================================
# FILTROS - AJUSTE CONFORME NECESSÁRIO
# Listas de nomes de PDFs e pastas que devem ser
# ignorados durante a varredura de arquivos.
# Útil para excluir templates, montagens e revisões.
# ============================================

# PDFs modelo/template que não devem ser impressos
IGNORAR_PDFS = ["ENG - 011 - 510000000 - NOME PEÇA - P1-1 - V0",
                "ENG - 011 - 510000000 - NOME PEÇA - P1-1 - V1",
                "ENG - 011 - 510000000 - NOME PEÇA - P1-1 - V2"]

# Pastas que contêm documentos de montagem ou revisão (não devem ser escaneadas)
IGNORAR_PASTAS = ["- 003 -", "003 - MONTAGEM", "REVISAO", "REVISÃO"]

"""Quando iniciamos a aplicação, a última linha possui a chamada de execução do uvicorn,
dentro dessa chamada existem 3 parâmetros (app, host="0.0.0.0", port=8080)

port = é a porta que a aplicação estará rodando
host = no exemplo acima qualquer pc na rede conseguirá acessar a aplicação, mas caso eu coloque meu IP, somente eu conseguirei acesso
app = é a  (objeto) que esta atribuída o FastAPI, o próprio FastAPI será quem organiza as rotas, no caso chega uma requisição /algumacoisa o FastAPI saberá
    direcionar o que precisa ser "servido" para a requisição
"""
app = FastAPI(title="FastPrint - Linea Brasil")

# ============================================
# CONFIGURAÇÕES
# Parâmetros de execução e caminhos das pastas
# compartilhadas onde os produtos estão armazenados.
# ============================================

# Interpretador de argumentos de linha de comando
parser = argparse.ArgumentParser(description="Script de impressão automatizada.")

# Argumento para alternar entre ambiente de teste (local) e produção (rede)
parser.add_argument(
    "--ambiente", 
    type=str, 
    default="producao", 
    help="Define o ambiente de execução (teste ou producao)"
)

args = parser.parse_args()

# Define os caminhos de busca de acordo com o ambiente selecionado
if args.ambiente == "teste":
    # Ambiente de teste: usa pasta local para simulação
    SEARCH_PATHS = ["/mnt/c/shared"]
else:
    # Ambiente de produção: pastas compartilhadas na rede (servidor de arquivos)
    SEARCH_PATHS = [
        "/mnt/xeon/Linea Brasil/6 Pesquisa e Desenvolvimento/1 - DOCUMENTOS/1 - DOCUMENTOS TECNICOS/1 - EM LINHA",
        "/mnt/xeon/Linea Brasil/6 Pesquisa e Desenvolvimento/1 - DOCUMENTOS/1 - DOCUMENTOS TECNICOS/3 - EM REVISAO",
    ]

logger.info(f"Ambiente: {args.ambiente} | Caminhos de busca: {SEARCH_PATHS}")


# Impressora padrão (None = usa a padrão do sistema CUPS)
DEFAULT_PRINTER: Optional[str] = None

# ============================================
# MODELS (Modelos de Dados)
# Esquemas de validação para as requisições
# recebidas pela API usando Pydantic.
# ============================================

# Requisição de impressão: recebe pasta, impressora, arquivos selecionados e fase
class PrintRequest(BaseModel):
    folder_path: str
    printer: Optional[str] = None
    selected_files: Optional[list[str]] = None
    fase: Optional[str] = None  # "Lote Teste", "Lote Piloto", "Lote Padrão"

# Requisição para listar PDFs de uma pasta
class FolderRequest(BaseModel):
    path: str

# Requisição para atualizar o status de um documento rastreado
class StatusUpdateRequest(BaseModel):
    codigo_rastreio: str
    novo_status: str  # "baixado"

# Requisição para atualizar a fase de produção de um documento
class FaseUpdateRequest(BaseModel):
    codigo_rastreio: str
    fase: str  # "Lote Teste", "Lote Piloto", "Lote Padrão"
    por_produto: bool = False

# ============================================
# FUNÇÕES AUXILIARES
# Funções utilitárias usadas pelas rotas da API
# para identificação de máquina, impressoras e
# manipulação de arquivos PDF.
# ============================================

#Essa função está sendo chamada em mais 2 funções que a utilizam
DRIVE_MAP = {
    "l": "/mnt/xeon",
    "c": "/mnt/c",
}

def normalize_path(path: str) -> str:
    """Converte paths Windows (L:\\...) para caminhos WSL (/mnt/xeon/...)."""
    if len(path) >= 2 and path[1] == ":":
        drive = path[0].lower()
        rest = path[2:].replace("\\", "/")
        base = DRIVE_MAP.get(drive, f"/mnt/{drive}")
        return base + rest
    return path.replace("\\", "/")


def get_hostname() -> str:
    """Retorna o nome do computador que está executando a aplicação."""
    try:
        """Usamos o socket.hostname para retornar o computador que está imprimindo os documentos
        porem o que o gethostname está retornando é o PC da onde a aplicação esta rodando, ai temos um PROBLEMA
        porque ou vai retornar sempre o nome do meu PC na Linea ou se algum dia estiver em servidor irá retornar o nome do Servidor na REDE"""
        return socket.gethostname()
    except:
        return "DESCONHECIDO"

#Essa função está sendo chamada em mais 1 função
def get_available_printers() -> list[str]:
    """Lista as impressoras disponíveis no sistema via CUPS."""
    try:
        import cups
        conn = cups.Connection()
        printers = conn.getPrinters()

        logger.info(f"Impressoras disponíveis: {list(printers.keys()) if printers else 'nenhuma'}")
        return list(printers.keys()) if printers else ["Impressora Padrão"]
    
    except Exception as e:
        logger.warning(f"Erro ao listar impressoras via CUPS: {e}")
        return ["Impressora Padrão"]


def find_pdf_files(folder_path: str) -> list[dict]:
    """
    Varre a pasta do produto em busca de arquivos PDF dentro de subpastas ENG.
    Ignora PDFs e pastas configurados nas listas de filtros.
    Retorna lista de dicts com nome, caminho, pasta e tamanho de cada PDF.
    """
    path = Path(folder_path)
    logger.info(f"Iniciando varredura de PDFs na pasta: {folder_path}")

    if not path.exists():
        logger.error(f"Pasta não encontrada: {folder_path}")
        raise FileNotFoundError(f"Pasta não encontrada: {folder_path}")

    pdf_files = []

    # Verifica se o nome da pasta segue o padrão de engenharia (ex: "ENG - 001 - ...")
    # Verifica mais de uma nomenclatura, porque como salvamos o nome do PDF de forma manual pode ocorrer erros
    def is_eng_folder(name: str) -> bool:
        upper_name = name.upper()
        return (upper_name.startswith("ENG -") or
                upper_name.startswith("ENG-") or
                upper_name == "ENG")

    # Verifica se a pasta deve ser ignorada (montagem, revisão, etc.)
    # def should_ignore_folder(name: str) -> bool:
    #     upper_name = name.upper()
    #     return any(termo in upper_name for termo in IGNORAR_PASTAS)

    def pastas_ignoradas(name):
        upper_name = name.upper()

        # IGNORAR_PASTAS = ["- 003 -", "003 - MONTAGEM", "REVISAO", "REVISÃO"]
        # Termo vai fazer o loop dentro desse array e verificar se o upper_name passado pra função tem aqui dentro
        for termo in IGNORAR_PASTAS:
            if termo in upper_name:
                return True

        return False

    # Verifica se o PDF é um template/modelo que deve ser ignorado
    # def should_ignore_pdf(name: str) -> bool:
    #     upper_name = name.upper()
    #     return any(termo in upper_name for termo in IGNORAR_PDFS)
    
    def ignorar_pdf(name):
        upper_name = name.upper()

        # IGNORAR_PDFS = ["ENG - 011 - 510000000 - NOME PEÇA - P1-1 - V0",
        #                 "ENG - 011 - 510000000 - NOME PEÇA - P1-1 - V1",
        #                 "ENG - 011 - 510000000 - NOME PEÇA - P1-1 - V2"]
        # Termo vai fazer o loop dentro desse array e verificar se o upper_name passado pra função tem aqui dentro
        for termo in IGNORAR_PDFS:
            if termo in upper_name:
                return True

        return False

    # Função recursiva que percorre subpastas coletando PDFs
    def scan_folder(folder: Path, parent_name: str = ""):
        for item in folder.iterdir():
            if item.is_file() and item.suffix.lower() == ".pdf":
                if ignorar_pdf(item.name):
                    continue
                display_folder = parent_name or folder.name
                pdf_files.append({
                    "name": item.name,
                    "path": str(item),
                    "folder": display_folder,
                    "size_kb": round(item.stat().st_size / 1024, 1)
                })
            elif item.is_dir() and not pastas_ignoradas(item.name):
                scan_folder(item, parent_name or folder.name)

    # Percorre as subpastas da raiz buscando pastas ENG
    for subdir in path.iterdir():
        if subdir.is_dir() and is_eng_folder(subdir.name) and not pastas_ignoradas(subdir.name):
            scan_folder(subdir)

    # Caso a própria pasta raiz seja uma pasta ENG, escaneia seus PDFs diretos
    if is_eng_folder(path.name):
        for item in path.iterdir():
            if item.is_file() and item.suffix.lower() == ".pdf":
                if not ignorar_pdf(item.name):
                    pdf_files.append({
                        "name": item.name,
                        "path": str(item),
                        "folder": path.name,
                        "size_kb": round(item.stat().st_size / 1024, 1)
                    })

    logger.info(f"Varredura concluída: {len(pdf_files)} PDF(s) encontrado(s) em '{folder_path}'")
    return sorted(pdf_files, key=lambda x: (x["folder"], x["name"]))


def stamp_pdf(pdf_path: str, codigo_rastreio: str, fase: str = None, usuario: str = None) -> str | None:
    """
    Adiciona carimbo de rastreio no topo de cada página do PDF.
    O carimbo contém: código de rastreio, fase de produção, data/hora e nome do computador.
    Lê o tamanho e rotação reais de cada página para posicionar o carimbo corretamente.
    Retorna o caminho do arquivo temporário carimbado, ou None em caso de falha.
    Requer pypdf e reportlab instalados.
    """
    logger.info(f"Carimbando PDF: {pdf_path} | Código: {codigo_rastreio} | Fase: {fase}")
    try:
        from pypdf import PdfReader, PdfWriter
        from reportlab.pdfgen import canvas
        import io

        reader = PdfReader(pdf_path)
        writer = PdfWriter()

        # Monta o texto do carimbo com código, fase, data e computador
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

        # Salva o PDF carimbado em arquivo temporário para enviar à impressora
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf", prefix=f"fp_{codigo_rastreio}_")
        with open(tmp.name, "wb") as f:
            writer.write(f)

        logger.info(f"PDF carimbado salvo em: {tmp.name}")
        return tmp.name

    except ImportError:
        logger.warning("pypdf ou reportlab não instalado. Imprimindo sem carimbo.")
        return None
    except Exception as e:
        logger.error(f"Erro ao carimbar PDF '{pdf_path}': {e}")
        return None


def print_pdf(pdf_path: str, printer: Optional[str] = None) -> dict:
    """
    Envia um arquivo PDF para impressão via CUPS.
    Seleciona a impressora especificada ou utiliza a padrão do sistema.
    Retorna dict com status de sucesso/falha e mensagem descritiva.
    """
    start_time = time.perf_counter()
    logger.info(f"Iniciando processo de impressão: {pdf_path}")

    if not Path(pdf_path).exists():
        logger.error(f"Arquivo não encontrado no caminho especificado: {pdf_path}")
        return {"success": False, "error": f"Arquivo não encontrado: {pdf_path}"}

    try:
        import cups
        conn = cups.Connection()

        if printer:
            printer_name = printer
            logger.info(f"Enviando para impressora específica: {printer}")
        else:
            printer_name = conn.getDefault()
            if not printer_name:
                printers = conn.getPrinters()
                if printers:
                    printer_name = list(printers.keys())[0]
                else:
                    logger.error("Nenhuma impressora disponível no CUPS.")
                    return {"success": False, "error": "Nenhuma impressora disponível"}
            logger.info(f"Enviando para impressora padrão: {printer_name}")

        process_start = time.perf_counter()
        job_id = conn.printFile(printer_name, pdf_path, Path(pdf_path).name, {})
        process_duration = time.perf_counter() - process_start

        total_duration = time.perf_counter() - start_time

        if job_id > 0:
            logger.info(f"Sucesso! Job ID: {job_id} | Tempo: {process_duration:.2f}s | Tempo total: {total_duration:.2f}s")
            return {"success": True, "message": f"Enviado para impressão: {Path(pdf_path).name}"}
        else:
            logger.error("Falha ao criar job de impressão no CUPS.")
            return {"success": False, "error": "Falha ao criar job de impressão"}

    except Exception as e:
        logger.exception(f"Erro inesperado durante a execução: {e}")
        return {"success": False, "error": str(e)}

# ============================================
# ROTAS DA API
# Endpoints REST que o frontend consome para
# buscar produtos, listar PDFs, imprimir,
# rastrear documentos e exibir o dashboard.
# ============================================

# --- LOGS ---

@app.get("/api/logs")
async def get_logs(limite: int = 100):
    """Retorna os últimos logs de impressão."""
    logger.info(f"Consultando logs (limite={limite})")
    return {"logs": listar_logs(limite)}

# --- RASTREIO DE DOCUMENTOS ---

@app.get("/api/documentos")
async def get_documentos(status: str = None, limite: int = 200):
    """Lista documentos impressos, opcionalmente filtrados por status."""
    logger.info(f"Listando documentos (status={status}, limite={limite})")
    docs = listar_documentos(status=status, limite=limite)
    return {"documentos": docs, "total": len(docs)}

@app.post("/api/documentos/status")
async def update_status(request: StatusUpdateRequest):
    """Atualiza o status de um documento (ex: entregue → baixado)."""
    logger.info(f"Atualizando status do documento {request.codigo_rastreio} para '{request.novo_status}'")
    usuario_id = get_or_create_sistema_user()
    ok = atualizar_status_documento(request.codigo_rastreio, request.novo_status, usuario_id)
    if not ok:
        logger.warning(f"Falha ao atualizar status: documento {request.codigo_rastreio} não encontrado ou transição inválida")
        raise HTTPException(status_code=400, detail="Documento não encontrado ou status inválido para esta transição")
    doc = buscar_documento(request.codigo_rastreio)
    logger.info(f"Status do documento {request.codigo_rastreio} atualizado com sucesso")
    return {"success": True, "documento": doc}

@app.post("/api/documentos/fase")
async def update_fase(request: FaseUpdateRequest):
    """Define a fase de produção de um documento (Lote Teste, Piloto ou Padrão)."""
    logger.info(f"Atualizando fase do documento {request.codigo_rastreio} para '{request.fase}' (por_produto={request.por_produto})")
    fases_validas = ["Lote Teste", "Lote Piloto", "Lote Padrão"]
    if request.fase not in fases_validas:
        logger.warning(f"Fase inválida recebida: '{request.fase}'")
        raise HTTPException(status_code=400, detail="Fase inválida")
    affected = atualizar_fase_documento(request.codigo_rastreio, request.fase, request.por_produto)
    if affected == 0:
        logger.warning(f"Documento {request.codigo_rastreio} não encontrado para atualização de fase")
        raise HTTPException(status_code=404, detail="Documento não encontrado")
    logger.info(f"Fase atualizada: {affected} documento(s) afetado(s)")
    return {"success": True, "affected": affected}

@app.get("/api/documentos/{codigo}")
async def get_documento(codigo: str):
    """Busca um documento específico pelo código de rastreio."""
    doc = buscar_documento(codigo)
    if not doc:
        raise HTTPException(status_code=404, detail="Documento não encontrado")
    return doc

# --- IMPRESSÃO ---

@app.get("/", response_class=HTMLResponse)
async def root():
    """Serve a página principal da aplicação (SPA)."""
    return FileResponse("static/index.html")

@app.get("/api/printers")
async def list_printers():
    """Retorna a lista de impressoras disponíveis no sistema."""
    printers = get_available_printers()
    return {"printers": printers, "default": DEFAULT_PRINTER}

@app.post("/api/list-pdfs")
async def list_pdfs(request: FolderRequest):
    """Escaneia uma pasta de produto e retorna a lista de PDFs encontrados."""
    try:
        pdfs = find_pdf_files(normalize_path(request.path))
        logger.info(f"Listagem de PDFs: {len(pdfs)} arquivo(s) em '{request.path}'")
        return {"success": True, "folder": request.path, "total": len(pdfs), "files": pdfs}
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Erro ao listar PDFs em '{request.path}': {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/print")
async def print_files(request: PrintRequest):
    """
    Rota principal de impressão. Para cada PDF selecionado:
    1. Gera código de rastreio único
    2. Carimba o PDF com informações de rastreio
    3. Envia para a impressora via CUPS
    4. Registra o documento no banco de dados para rastreio
    """
    request.folder_path = normalize_path(request.folder_path)
    logger.info(f"Requisição de impressão: pasta='{request.folder_path}', impressora='{request.printer}', "
                f"fase='{request.fase}', arquivos={len(request.selected_files or [])}")
    try:
        # Usa os arquivos selecionados pelo usuário ou escaneia toda a pasta
        if request.selected_files:
            pdfs = [{"path": normalize_path(f), "name": Path(f).name} for f in request.selected_files]
        else:
            pdfs = find_pdf_files(request.folder_path)

        if not pdfs:
            logger.warning("Nenhum PDF encontrado para impressão")
            return {"success": False, "message": "Nenhum PDF para imprimir"}

        usuario_id   = get_or_create_sistema_user()
        computador   = get_hostname()
        produto      = Path(request.folder_path).name
        logger.info(f"Processando {len(pdfs)} PDF(s) do produto '{produto}' no computador '{computador}'")

        results = []
        success_count = 0
        codigos_gerados = []
        arquivos_tmp = []

        for pdf in pdfs:
            # Gera código de rastreio único para cada documento
            codigo = gerar_codigo_rastreio(computador)

            # Carimba o PDF com informações de rastreio (retorna caminho do arquivo temporário)
            pdf_para_imprimir = stamp_pdf(pdf["path"], codigo, request.fase, computador)
            usou_tmp = pdf_para_imprimir is not None

            if not usou_tmp:
                # Se o carimbo falhou, imprime o PDF original sem carimbo
                pdf_para_imprimir = pdf["path"]
            else:
                arquivos_tmp.append(pdf_para_imprimir)

            # Envia o PDF para a impressora
            result = print_pdf(pdf_para_imprimir, request.printer)
            result["codigo_rastreio"] = codigo
            results.append({"file": pdf["name"], **result})

            if result["success"]:
                success_count += 1
                codigos_gerados.append(codigo)
                # Registra o documento no banco para rastreio
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

        # Limpa os arquivos temporários carimbados após a impressão
        for tmp in arquivos_tmp:
            try:
                os.unlink(tmp)
            except:
                pass

        # Registra log geral da operação de impressão
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

        logger.info(f"Impressão concluída: {success_count}/{len(pdfs)} PDF(s) impressos com sucesso")
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
        logger.exception(f"Erro inesperado durante impressão: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/search")
async def search_products(query: str = ""):
    """
    Busca produtos nas pastas compartilhadas da rede.
    Percorre os SEARCH_PATHS procurando pastas cujo nome contenha a query.
    Produtos são identificados por terem código numérico de 9 dígitos no início do nome.
    """
    if not query or len(query) < 3:
        return {"success": False, "message": "Digite pelo menos 3 caracteres", "results": []}

    logger.info(f"Buscando produtos com query: '{query}'")
    results = []

    for search_path in SEARCH_PATHS:
        status_path = Path(search_path)
        if not status_path.exists():
            logger.warning(f"Caminho de busca não encontrado: {search_path}")
            continue

        # Extrai o nome do status da pasta (ex: "EM LINHA", "EM REVISAO")
        status_name = status_path.name.split(" - ")[1] if " - " in status_path.name else status_path.name

        for item in status_path.iterdir():
            if not item.is_dir():
                continue

            # Verifica se é um produto (código de 9 dígitos no início do nome)
            is_product = item.name[:9].isdigit() and len(item.name) >= 9

            if is_product:
                # Busca direta na pasta do produto
                if query.upper() in item.name.upper():
                    pdf_count = sum(1 for sub in item.iterdir()
                                   if sub.is_dir() and sub.name.upper().startswith("ENG")
                                   for p in sub.rglob("*.pdf") if not any(termo in str(p).upper() for termo in IGNORAR_PASTAS))
                    results.append({
                        "name": item.name, "path": str(item),
                        "type": "PRODUTO", "status": status_name, "pdf_count": pdf_count
                    })
            else:
                # Busca em subpastas (pastas agrupadas por categoria)
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
    logger.info(f"Busca por '{query}': {len(results)} produto(s) encontrado(s)")
    return {"success": True, "query": query, "total": len(results), "results": results[:20]}


@app.get("/api/browse")
async def browse_folder(path: str = ""):
    """Navega pelas pastas compartilhadas, listando subpastas e contando PDFs em pastas ENG."""
    try:
        if not path:
            path = SEARCH_PATHS[0]

        folder = Path(normalize_path(path))
        logger.info(f"Navegando pasta: {folder}")

        if not folder.exists():
            raise HTTPException(status_code=404, detail="Pasta não encontrada")

        items = []
        for item in sorted(folder.iterdir()):
            if item.is_dir():
                # Conta os PDFs dentro das subpastas ENG de cada item
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
        logger.error(f"Sem permissão para acessar: {path}")
        raise HTTPException(status_code=403, detail="Sem permissão para acessar esta pasta")
    except Exception as e:
        logger.error(f"Erro ao navegar pasta '{path}': {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Monta os arquivos estáticos (HTML, CSS, JS) para o frontend
app.mount("/static", StaticFiles(directory="static"), name="static")


"""Ponto de entrada: inicia o servidor Uvicorn na porta 8080
# o __name__ recebr main é uma atribuição do Python, logo sempre que rodarmos python main.py
esse if será executado """

if __name__ == "__main__":
    import uvicorn

    # Inicializa o banco de dados (cria tabelas se necessário) -- ESTUDAR A CHAMADA PRO BANCO DE DADOS, COMO VERIFICA SE JÁ ESTÃO CRIADAS AS TABELAS?
    from database import init_db
    init_db()

    # Aqui são logs e print normal quando inicia a aplicação
    logger.info("Iniciando servidor FastPrint...")
    print(f"Acesse: http://localhost:8080")
    print(f"\nPara a equipe acessar, use seu IP local:")
    print(f"   http://SEU_IP:8080")

    uvicorn.run(app, host="0.0.0.0", port=8080)
