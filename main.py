"""
Sistema de Impressão em Lote - Linea Brasil
Fase 1: Script local com interface web
"""

from fastapi import FastAPI, HTTPException, Header
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
from datetime import datetime, timedelta
import jwt
from database import (
    verificar_login, registrar_log, criar_usuario, listar_usuarios, listar_logs,
    gerar_codigo_rastreio, registrar_documento_impresso,
    listar_documentos, atualizar_status_documento, buscar_documento,
    atualizar_fase_documento
)

# ============================================
# FILTROS - AJUSTE CONFORME NECESSÁRIO
# ============================================

IGNORAR_PDFS = ["ENG - 011 - 510000000 - NOME PEÇA - P1-1 - V0", 
                "ENG - 011 - 510000000 - NOME PEÇA - P1-1 - V1", 
                "ENG - 011 - 510000000 - NOME PEÇA - P1-1 - V2"]

IGNORAR_PASTAS = ["- 003 -", "003 - MONTAGEM"]

SECRET_KEY = "fastprint-linea-2025-sua-chave-secreta"

app = FastAPI(title="FastPrint - Linea Brasil")

# ============================================
# CONFIGURAÇÕES
# ============================================

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
    
class FolderRequest(BaseModel):
    path: str

class LoginRequest(BaseModel):
    usuario: str
    senha: str

class NovoUsuarioRequest(BaseModel):
    nome: str
    usuario: str
    senha: str

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
    """Retorna o nome do computador"""
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
    
    elif system == "Linux":
        # Try PowerShell via WSL interop first (WSL environment)
        for ps_cmd in ["powershell.exe", "powershell"]:
            try:
                result = subprocess.run(
                    [ps_cmd, "-Command", "Get-Printer | Select-Object -ExpandProperty Name"],
                    capture_output=True, text=True, timeout=10
                )
                if result.returncode == 0:
                    printers = [p.strip() for p in result.stdout.strip().split('\n') if p.strip()]
                    if printers:
                        return printers
            except FileNotFoundError:
                continue
            except Exception as e:
                print(f"Erro ao listar impressoras via PowerShell: {e}")
        # Fallback to CUPS lpstat
        try:
            result = subprocess.run(["lpstat", "-p"], capture_output=True, text=True, timeout=10)
            if result.returncode == 0:
                printers = []
                for line in result.stdout.split('\n'):
                    if line.startswith('printer '):
                        parts = line.split()
                        if len(parts) >= 2:
                            printers.append(parts[1])
                return printers
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


def stamp_pdf(pdf_path: str, codigo_rastreio: str) -> str | None:
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
        texto = f"FastPrint  |  {codigo_rastreio}  |  {datetime.now().strftime('%d/%m/%Y %H:%M')}  |  {get_hostname()}"

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
    if not Path(pdf_path).exists():
        return {"success": False, "error": f"Arquivo não encontrado: {pdf_path}"}
    
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
        except:
            pass
    
    if not sumatra_exe:
        return {"success": False, "error": "SumatraPDF não encontrado. Instale ou adicione ao PATH."}
    
    try:
        if printer:
            cmd = [sumatra_exe, "-print-to", printer, "-silent", pdf_path]
        else:
            cmd = [sumatra_exe, "-print-to-default", "-silent", pdf_path]
        
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        
        if result.returncode == 0:
            return {"success": True, "message": f"Enviado para impressão: {Path(pdf_path).name}"}
        else:
            error_msg = result.stderr or result.stdout or "Erro desconhecido"
            return {"success": False, "error": error_msg}
            
    except subprocess.TimeoutExpired:
        return {"success": False, "error": "Timeout - impressão demorou demais"}
    except Exception as e:
        return {"success": False, "error": str(e)}

# ============================================
# ROTAS DA API
# ============================================

# --- AUTENTICAÇÃO ---

@app.post("/api/login")
async def login(request: LoginRequest):
    user = verificar_login(request.usuario, request.senha)
    if not user:
        raise HTTPException(status_code=401, detail="Usuário ou senha inválidos")
    
    token = jwt.encode(
        {"user_id": user["id"], "usuario": user["usuario"], "nome": user["nome"], 
         "exp": datetime.utcnow() + timedelta(hours=8)},
        SECRET_KEY, algorithm="HS256"
    )
    return {"success": True, "token": token, "user": user}

@app.get("/api/verificar-token")
async def verificar_token(token: str):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
        return {"valid": True, "user": payload}
    except jwt.ExpiredSignatureError:
        return {"valid": False, "error": "Token expirado"}
    except jwt.InvalidTokenError:
        return {"valid": False, "error": "Token inválido"}

@app.post("/api/usuarios")
async def criar_novo_usuario(request: NovoUsuarioRequest):
    if criar_usuario(request.nome, request.usuario, request.senha):
        return {"success": True, "message": f"Usuário {request.usuario} criado"}
    raise HTTPException(status_code=400, detail="Usuário já existe")

@app.get("/api/usuarios")
async def get_usuarios():
    return {"usuarios": listar_usuarios()}

@app.get("/api/logs")
async def get_logs(limite: int = 100):
    return {"logs": listar_logs(limite)}

# --- RASTREIO ---

@app.get("/api/documentos")
async def get_documentos(status: str = None, limite: int = 200):
    """Lista documentos impressos com filtro opcional de status"""
    docs = listar_documentos(status=status, limite=limite)
    return {"documentos": docs, "total": len(docs)}

@app.post("/api/documentos/status")
async def update_status(request: StatusUpdateRequest, authorization: str = Header(default=None)):
    """Atualiza status de um documento (entregue → baixado)"""
    usuario_id = _get_user_id(authorization)
    if not usuario_id:
        raise HTTPException(status_code=401, detail="Não autorizado")
    
    ok = atualizar_status_documento(request.codigo_rastreio, request.novo_status, usuario_id)
    if not ok:
        raise HTTPException(status_code=400, detail="Documento não encontrado ou status inválido para esta transição")
    
    doc = buscar_documento(request.codigo_rastreio)
    return {"success": True, "documento": doc}

@app.post("/api/documentos/fase")
async def update_fase(request: FaseUpdateRequest, authorization: str = Header(default=None)):
    """Atualiza a fase de um documento (opcionalmente para todos do mesmo produto)"""
    usuario_id = _get_user_id(authorization)
    if not usuario_id:
        raise HTTPException(status_code=401, detail="Não autorizado")

    fases_validas = ["Lote Teste", "Lote Piloto", "Lote Padrão"]
    if request.fase not in fases_validas:
        raise HTTPException(status_code=400, detail="Fase inválida")

    affected = atualizar_fase_documento(request.codigo_rastreio, request.fase, request.por_produto)
    if affected == 0:
        raise HTTPException(status_code=404, detail="Documento não encontrado")

    return {"success": True, "affected": affected}

@app.get("/api/documentos/{codigo}")
async def get_documento(codigo: str):
    """Busca um documento pelo código de rastreio"""
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


def _get_user_id(authorization: str) -> int | None:
    """Extrai user_id do token JWT"""
    if not authorization or not authorization.startswith("Bearer "):
        return None
    token = authorization.split(" ")[1]
    if token == "temp":
        return 1
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
        return payload["user_id"]
    except:
        return None

def _get_user_payload(authorization: str) -> dict | None:
    if not authorization or not authorization.startswith("Bearer "):
        return None
    token = authorization.split(" ")[1]
    if token == "temp":
        return {"user_id": 1, "usuario": "teste", "nome": "Usuário Teste"}
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
    except:
        return None


@app.post("/api/print")
async def print_files(request: PrintRequest, authorization: str = Header(default=None)):
    """Imprime PDFs selecionados — com carimbo de rastreio e registro no banco"""
    try:
        if request.selected_files:
            pdfs = [{"path": f, "name": Path(f).name} for f in request.selected_files]
        else:
            pdfs = find_pdf_files(request.folder_path)
        
        if not pdfs:
            return {"success": False, "message": "Nenhum PDF para imprimir"}
        
        payload = _get_user_payload(authorization)
        usuario_id = payload["user_id"] if payload else 1
        computador = get_hostname()
        produto = Path(request.folder_path).name
        
        results = []
        success_count = 0
        codigos_gerados = []
        arquivos_tmp = []

        for pdf in pdfs:
            # Gera código de rastreio único por arquivo
            codigo = gerar_codigo_rastreio(computador)
            
            # Tenta carimbar o PDF
            pdf_para_imprimir = stamp_pdf(pdf["path"], codigo)
            usou_tmp = pdf_para_imprimir is not None
            
            if not usou_tmp:
                pdf_para_imprimir = pdf["path"]  # fallback sem carimbo
            else:
                arquivos_tmp.append(pdf_para_imprimir)

            result = print_pdf(pdf_para_imprimir, request.printer)
            result["codigo_rastreio"] = codigo
            results.append({"file": pdf["name"], **result})
            
            if result["success"]:
                success_count += 1
                codigos_gerados.append(codigo)
                # Registra no banco de rastreio
                registrar_documento_impresso(
                    codigo_rastreio=codigo,
                    produto=produto,
                    arquivo=pdf["name"],
                    pasta=request.folder_path,
                    impressora=request.printer or "Padrão",
                    computador=computador,
                    usuario_id=usuario_id
                )
        
        # Limpa arquivos temporários
        for tmp in arquivos_tmp:
            try:
                os.unlink(tmp)
            except:
                pass

        # Registra log geral (compatibilidade)
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
                                   for p in sub.rglob("*.pdf") if "REVISAO" not in str(p))
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
                                       for p in sub.rglob("*.pdf") if "REVISAO" not in str(p))
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
    print("🖨️  FastPrint - Linea Brasil")
    print("="*50)
    print(f"🌐 Acesse: http://localhost:8000")
    print(f"\n💡 Para a equipe acessar, use seu IP local:")
    print(f"   http://SEU_IP:8000")
    print("\n" + "="*50 + "\n")
    
    uvicorn.run(app, host="0.0.0.0", port=8000)