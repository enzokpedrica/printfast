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
from typing import Optional
from datetime import datetime, timedelta
import jwt
from database import verificar_login, registrar_log, criar_usuario, listar_usuarios, listar_logs

# Chave secreta para JWT (troque por algo único)
SECRET_KEY = "fastprint-linea-2025-sua-chave-secreta"

app = FastAPI(title="FastPrint - Linea Brasil")

# ============================================
# CONFIGURAÇÕES - AJUSTE CONFORME NECESSÁRIO
# ============================================

# Caminho base onde ficam os produtos
# Caminhos onde buscar produtos
SEARCH_PATHS = [
    r"L:\Linea Brasil\6 Pesquisa e Desenvolvimento\1 - DOCUMENTOS\1 - DOCUMENTOS TECNICOS\1 - EM LINHA",
    r"L:\Linea Brasil\6 Pesquisa e Desenvolvimento\1 - DOCUMENTOS\1 - DOCUMENTOS TECNICOS\3 - EM REVISAO",
]

# Impressora padrão (deixe None para usar a padrão do sistema)
DEFAULT_PRINTER: Optional[str] = None

# ============================================
# MODELS
# ============================================

class PrintRequest(BaseModel):
    folder_path: str
    printer: Optional[str] = None
    selected_files: Optional[list[str]] = None  # Lista de caminhos específicos para imprimir
    
class FolderRequest(BaseModel):
    path: str

class LoginRequest(BaseModel):
    usuario: str
    senha: str

class NovoUsuarioRequest(BaseModel):
    nome: str
    usuario: str
    senha: str    

# ============================================
# FUNÇÕES AUXILIARES
# ============================================

def get_available_printers() -> list[str]:
    """Lista impressoras disponíveis no sistema"""
    system = platform.system()
    
    if system == "Windows":
        try:
            # Usa PowerShell para listar impressoras
            result = subprocess.run(
                ["powershell", "-Command", "Get-Printer | Select-Object -ExpandProperty Name"],
                capture_output=True,
                text=True,
                timeout=10
            )
            if result.returncode == 0:
                printers = [p.strip() for p in result.stdout.strip().split('\n') if p.strip()]
                return printers
        except Exception as e:
            print(f"Erro ao listar impressoras: {e}")
    
    elif system == "Linux":
        try:
            result = subprocess.run(
                ["lpstat", "-p"],
                capture_output=True,
                text=True,
                timeout=10
            )
            if result.returncode == 0:
                # Parse output: "printer PrinterName is idle..."
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
    """
    Encontra todos os PDFs em subpastas que começam com 'ENG'
    Suporta formato: ENG - 002 - FURACAO, ENG-DESENHOS, etc.
    Também busca recursivamente em subpastas de ENG
    """
    path = Path(folder_path)
    
    if not path.exists():
        raise FileNotFoundError(f"Pasta não encontrada: {folder_path}")
    
    pdf_files = []
    
    def is_eng_folder(name: str) -> bool:
        """Verifica se a pasta começa com ENG (vários formatos)"""
        upper_name = name.upper()
        return (upper_name.startswith("ENG -") or 
                upper_name.startswith("ENG-") or 
                upper_name == "ENG")
    
    def scan_folder(folder: Path, parent_name: str = ""):
        """Escaneia pasta e subpastas recursivamente"""
        for item in folder.iterdir():
            if item.is_file() and item.suffix.lower() == ".pdf":
                display_folder = parent_name or folder.name
                pdf_files.append({
                    "name": item.name,
                    "path": str(item),
                    "folder": display_folder,
                    "size_kb": round(item.stat().st_size / 1024, 1)
                })
            elif item.is_dir() and item.name.upper() != "REVISAO":
                # Busca recursiva em subpastas (exceto REVISAO)
                scan_folder(item, parent_name or folder.name)
    
    # Procura em subpastas que começam com "ENG"
    for subdir in path.iterdir():
        if subdir.is_dir() and is_eng_folder(subdir.name):
            scan_folder(subdir)
    
    # Se a própria pasta passada for uma pasta ENG, busca PDFs diretamente nela
    if is_eng_folder(path.name):
        for item in path.iterdir():
            if item.is_file() and item.suffix.lower() == ".pdf":
                pdf_files.append({
                    "name": item.name,
                    "path": str(item),
                    "folder": path.name,
                    "size_kb": round(item.stat().st_size / 1024, 1)
                })
    
    return sorted(pdf_files, key=lambda x: (x["folder"], x["name"]))


def print_pdf(pdf_path: str, printer: Optional[str] = None) -> dict:
    """
    Envia um PDF para impressão usando SumatraPDF
    Retorna status da operação
    """
    
    if not Path(pdf_path).exists():
        return {"success": False, "error": f"Arquivo não encontrado: {pdf_path}"}
    
    # Possíveis caminhos do SumatraPDF
    sumatra_paths = [
        os.path.expandvars(r"%LOCALAPPDATA%\SumatraPDF\SumatraPDF.exe"),  # Caminho mais comum
        r"C:\Users\{}\AppData\Local\SumatraPDF\SumatraPDF.exe".format(os.environ.get('USERNAME', '')),
        r"C:\Program Files\SumatraPDF\SumatraPDF.exe",
        r"C:\Program Files (x86)\SumatraPDF\SumatraPDF.exe",
        "SumatraPDF.exe",  # Se estiver no PATH
    ]
    
    sumatra_exe = None
    for path in sumatra_paths:
        if Path(path).exists():
            sumatra_exe = path
            break
    
    if not sumatra_exe:
        # Tenta encontrar via where
        try:
            result = subprocess.run(
                ["where", "SumatraPDF.exe"],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0:
                sumatra_exe = result.stdout.strip().split('\n')[0]
        except:
            pass
    
    if not sumatra_exe:
        return {"success": False, "error": "SumatraPDF não encontrado. Instale ou adicione ao PATH."}
    
    try:
        # Monta o comando do SumatraPDF
        # -print-to "printer" = imprime na impressora especificada
        # -print-to-default = imprime na impressora padrão
        # -silent = não abre janela
        
        if printer:
            cmd = [sumatra_exe, "-print-to", printer, "-silent", pdf_path]
        else:
            cmd = [sumatra_exe, "-print-to-default", "-silent", pdf_path]
        
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=60
        )
        
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

# ============================================
# AUTENTICAÇÃO


@app.post("/api/login")
async def login(request: LoginRequest):
    """Faz login e retorna token JWT"""
    user = verificar_login(request.usuario, request.senha)
    if not user:
        raise HTTPException(status_code=401, detail="Usuário ou senha inválidos")
    
    # Gera token JWT válido por 8 horas
    token = jwt.encode(
        {"user_id": user["id"], "usuario": user["usuario"], "nome": user["nome"], 
         "exp": datetime.utcnow() + timedelta(hours=8)},
        SECRET_KEY,
        algorithm="HS256"
    )
    return {"success": True, "token": token, "user": user}

@app.get("/api/verificar-token")
async def verificar_token(token: str):
    """Verifica se o token é válido"""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
        return {"valid": True, "user": payload}
    except jwt.ExpiredSignatureError:
        return {"valid": False, "error": "Token expirado"}
    except jwt.InvalidTokenError:
        return {"valid": False, "error": "Token inválido"}

@app.post("/api/usuarios")
async def criar_novo_usuario(request: NovoUsuarioRequest):
    """Cria um novo usuário (admin)"""
    if criar_usuario(request.nome, request.usuario, request.senha):
        return {"success": True, "message": f"Usuário {request.usuario} criado"}
    raise HTTPException(status_code=400, detail="Usuário já existe")

@app.get("/api/usuarios")
async def get_usuarios():
    """Lista todos os usuários"""
    return {"usuarios": listar_usuarios()}

@app.get("/api/logs")
async def get_logs(limite: int = 100):
    """Lista os logs de impressão"""
    return {"logs": listar_logs(limite)}
# ============================================    

@app.get("/", response_class=HTMLResponse)
async def root():
    """Serve a página principal"""
    return FileResponse("static/index.html")


@app.get("/api/printers")
async def list_printers():
    """Lista impressoras disponíveis"""
    printers = get_available_printers()
    return {"printers": printers, "default": DEFAULT_PRINTER}


@app.post("/api/list-pdfs")
async def list_pdfs(request: FolderRequest):
    """Lista PDFs em uma pasta"""
    try:
        pdfs = find_pdf_files(request.path)
        return {
            "success": True,
            "folder": request.path,
            "total": len(pdfs),
            "files": pdfs
        }
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/print")
async def print_files(request: PrintRequest, authorization: str = Header(default=None)):
    """Imprime PDFs selecionados ou todos de uma pasta"""
    try:
        # Se tem arquivos selecionados, usa eles
        if request.selected_files:
            pdfs = [{"path": f, "name": Path(f).name} for f in request.selected_files]
        else:
            pdfs = find_pdf_files(request.folder_path)
        
        if not pdfs:
            return {
                "success": False,
                "message": "Nenhum PDF para imprimir"
            }
        
        results = []
        success_count = 0
        
        for pdf in pdfs:
            result = print_pdf(pdf["path"], request.printer)
            results.append({
                "file": pdf["name"],
                **result
            })
            if result["success"]:
                success_count += 1
        
        # Registra no log se tiver token válido
        if authorization and authorization.startswith("Bearer "):
            try:
                token = authorization.split(" ")[1]
                payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
                produto = Path(request.folder_path).name
                arquivos = [pdf["name"] for pdf in pdfs if any(r["file"] == pdf["name"] and r.get("success") for r in results)]
                registrar_log(
                    usuario_id=payload["user_id"],
                    produto=produto,
                    pasta=request.folder_path,
                    arquivos=arquivos,
                    impressora=request.printer or "Padrão"
                )
            except:
                pass  # Se falhar o log, não impede a impressão
        
        return {
            "success": success_count > 0,
            "total": len(pdfs),
            "printed": success_count,
            "failed": len(pdfs) - success_count,
            "results": results
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

            # Verifica se é um produto (código de 9 dígitos) ou categoria
            is_product = item.name[:9].isdigit() and len(item.name) >= 9

            if is_product:
                # É produto direto (ex: EM REVISAO)
                if query.upper() in item.name.upper():
                    pdf_count = sum(1 for sub in item.iterdir() 
                                   if sub.is_dir() and sub.name.upper().startswith("ENG")
                                   for p in sub.rglob("*.pdf") if "REVISAO" not in str(p))
                    
                    results.append({
                        "name": item.name,
                        "path": str(item),
                        "type": "PRODUTO",
                        "status": status_name,
                        "pdf_count": pdf_count
                    })
            else:
                # É categoria, busca produtos dentro (ex: EM LINHA)
                for product_folder in item.iterdir():
                    if not product_folder.is_dir():
                        continue
                    
                    if query.upper() in product_folder.name.upper():
                        pdf_count = sum(1 for sub in product_folder.iterdir() 
                                       if sub.is_dir() and sub.name.upper().startswith("ENG")
                                       for p in sub.rglob("*.pdf") if "REVISAO" not in str(p))
                        
                        results.append({
                            "name": product_folder.name,
                            "path": str(product_folder),
                            "type": "PRODUTO",
                            "status": status_name,
                            "pdf_count": pdf_count
                        })

    results.sort(key=lambda x: (x["status"], x["name"]))

    return {
        "success": True,
        "query": query,
        "total": len(results),
        "results": results[:20]
    }



@app.get("/api/browse")
async def browse_folder(path: str = ""):
    """Navega pelas pastas para facilitar a seleção"""
    try:
        if not path:
            path = SEARCH_PATHS[0]
        
        folder = Path(path)
        
        if not folder.exists():
            raise HTTPException(status_code=404, detail="Pasta não encontrada")
        
        items = []
        for item in sorted(folder.iterdir()):
            if item.is_dir():
                # Conta PDFs nas subpastas ENG
                pdf_count = 0
                for subdir in item.iterdir():
                    if subdir.is_dir() and subdir.name.upper().startswith("ENG"):
                        pdf_count += len(list(subdir.glob("*.pdf")))
                
                items.append({
                    "name": item.name,
                    "path": str(item),
                    "is_dir": True,
                    "pdf_count": pdf_count
                })
        
        return {
            "current": str(folder),
            "parent": str(folder.parent) if folder.parent != folder else None,
            "items": items
        }
        
    except PermissionError:
        raise HTTPException(status_code=403, detail="Sem permissão para acessar esta pasta")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# Monta arquivos estáticos
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
