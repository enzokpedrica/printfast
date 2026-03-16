"""
Banco de Dados
Gerencia usuários, logs de impressão e rastreio de documentos
"""

import sqlite3
from pathlib import Path
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash

DB_PATH = Path(__file__).parent / "fastprint.db"

def get_connection():
    """Retorna conexão com o banco"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """Cria as tabelas se não existirem"""
    conn = get_connection()
    cursor = conn.cursor()
    
    # Tabela de usuários
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS usuarios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT NOT NULL,
            usuario TEXT UNIQUE NOT NULL,
            senha_hash TEXT NOT NULL,
            ativo INTEGER DEFAULT 1,
            criado_em TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # Tabela de logs (mantida para compatibilidade)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            usuario_id INTEGER NOT NULL,
            data TEXT DEFAULT CURRENT_TIMESTAMP,
            produto TEXT,
            pasta TEXT,
            arquivos TEXT,
            quantidade INTEGER,
            impressora TEXT,
            FOREIGN KEY (usuario_id) REFERENCES usuarios(id)
        )
    """)

    # Tabela de documentos impressos (rastreio)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS documentos_impressos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            codigo_rastreio TEXT UNIQUE NOT NULL,
            produto TEXT NOT NULL,
            arquivo TEXT NOT NULL,
            pasta TEXT,
            impressora TEXT,
            computador TEXT,
            status TEXT DEFAULT 'entregue',
            impresso_por_id INTEGER NOT NULL,
            impresso_em TEXT DEFAULT CURRENT_TIMESTAMP,
            recolhido_por_id INTEGER,
            recolhido_em TEXT,
            baixado_por_id INTEGER,
            baixado_em TEXT,
            FOREIGN KEY (impresso_por_id) REFERENCES usuarios(id),
            FOREIGN KEY (recolhido_por_id) REFERENCES usuarios(id),
            FOREIGN KEY (baixado_por_id) REFERENCES usuarios(id)
        )
    """)

    # Contador diário para código de rastreio
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS contador_rastreio (
            data TEXT PRIMARY KEY,
            contador INTEGER DEFAULT 0
        )
    """)
    
    # Migration: coluna fase (caso banco já exista sem ela)
    try:
        cursor.execute("ALTER TABLE documentos_impressos ADD COLUMN fase TEXT DEFAULT NULL")
        conn.commit()
    except sqlite3.OperationalError:
        pass  # coluna já existe

    conn.commit()
    conn.close()

# ============================================
# USUÁRIOS
# ============================================

def criar_usuario(nome: str, usuario: str, senha: str) -> bool:
    try:
        conn = get_connection()
        cursor = conn.cursor()
        senha_hash = generate_password_hash(senha)
        cursor.execute(
            "INSERT INTO usuarios (nome, usuario, senha_hash) VALUES (?, ?, ?)",
            (nome, usuario, senha_hash)
        )
        conn.commit()
        conn.close()
        return True
    except sqlite3.IntegrityError:
        return False

def verificar_login(usuario: str, senha: str) -> dict | None:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id, nome, usuario, senha_hash, ativo FROM usuarios WHERE usuario = ?",
        (usuario,)
    )
    row = cursor.fetchone()
    conn.close()
    
    if row and row["ativo"] and check_password_hash(row["senha_hash"], senha):
        return {"id": row["id"], "nome": row["nome"], "usuario": row["usuario"]}
    return None

def listar_usuarios():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, nome, usuario, ativo, criado_em FROM usuarios")
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]

def desativar_usuario(usuario_id: int):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE usuarios SET ativo = 0 WHERE id = ?", (usuario_id,))
    conn.commit()
    conn.close()

def ativar_usuario(usuario_id: int):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE usuarios SET ativo = 1 WHERE id = ?", (usuario_id,))
    conn.commit()
    conn.close()

# ============================================
# LOGS (compatibilidade)
# ============================================

def registrar_log(usuario_id: int, produto: str, pasta: str, arquivos: list, impressora: str):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """INSERT INTO logs (usuario_id, produto, pasta, arquivos, quantidade, impressora) 
           VALUES (?, ?, ?, ?, ?, ?)""",
        (usuario_id, produto, pasta, ",".join(arquivos), len(arquivos), impressora)
    )
    conn.commit()
    conn.close()

def listar_logs(limite: int = 100):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT l.*, u.nome as usuario_nome 
        FROM logs l 
        JOIN usuarios u ON l.usuario_id = u.id 
        ORDER BY l.data DESC 
        LIMIT ?
    """, (limite,))
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]

# ============================================
# RASTREIO DE DOCUMENTOS
# ============================================

def gerar_codigo_rastreio(computador: str) -> str:
    """Gera código único: FP-AAAAMMDD-SEQ-PC"""
    hoje = datetime.now().strftime("%Y%m%d")
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute("INSERT OR IGNORE INTO contador_rastreio (data, contador) VALUES (?, 0)", (hoje,))
    cursor.execute("UPDATE contador_rastreio SET contador = contador + 1 WHERE data = ?", (hoje,))
    cursor.execute("SELECT contador FROM contador_rastreio WHERE data = ?", (hoje,))
    seq = cursor.fetchone()["contador"]
    conn.commit()
    conn.close()
    
    # Limita e limpa o nome do computador
    pc = "".join(c for c in computador.upper() if c.isalnum())[:8]
    return f"FP-{hoje}-{seq:04d}-{pc}"

def registrar_documento_impresso(
    codigo_rastreio: str,
    produto: str,
    arquivo: str,
    pasta: str,
    impressora: str,
    computador: str,
    usuario_id: int
):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO documentos_impressos 
        (codigo_rastreio, produto, arquivo, pasta, impressora, computador, impresso_por_id)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (codigo_rastreio, produto, arquivo, pasta, impressora, computador, usuario_id))
    conn.commit()
    conn.close()

def listar_documentos(status: str = None, limite: int = 200):
    conn = get_connection()
    cursor = conn.cursor()
    
    query = """
        SELECT
            d.*,
            u1.nome as impresso_por_nome,
            u2.nome as recolhido_por_nome,
            u3.nome as baixado_por_nome
        FROM documentos_impressos d
        JOIN usuarios u1 ON d.impresso_por_id = u1.id
        LEFT JOIN usuarios u2 ON d.recolhido_por_id = u2.id
        LEFT JOIN usuarios u3 ON d.baixado_por_id = u3.id
    """
    
    if status:
        query += " WHERE d.status = ?"
        cursor.execute(query + " ORDER BY d.impresso_em DESC LIMIT ?", (status, limite))
    else:
        cursor.execute(query + " ORDER BY d.impresso_em DESC LIMIT ?", (limite,))
    
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]

def atualizar_status_documento(codigo_rastreio: str, novo_status: str, usuario_id: int) -> bool:
    """Atualiza status: recolhido ou baixado"""
    conn = get_connection()
    cursor = conn.cursor()
    agora = datetime.now().isoformat()
    
    if novo_status == "baixado":
        cursor.execute("""
            UPDATE documentos_impressos
            SET status = 'baixado', baixado_por_id = ?, baixado_em = ?
            WHERE codigo_rastreio = ? AND status = 'entregue'
        """, (usuario_id, agora, codigo_rastreio))
    else:
        conn.close()
        return False
    
    affected = cursor.rowcount
    conn.commit()
    conn.close()
    return affected > 0

def buscar_documento(codigo_rastreio: str) -> dict | None:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT 
            d.*,
            u1.nome as impresso_por_nome,
            u2.nome as recolhido_por_nome,
            u3.nome as baixado_por_nome
        FROM documentos_impressos d
        JOIN usuarios u1 ON d.impresso_por_id = u1.id
        LEFT JOIN usuarios u2 ON d.recolhido_por_id = u2.id
        LEFT JOIN usuarios u3 ON d.baixado_por_id = u3.id
        WHERE d.codigo_rastreio = ?
    """, (codigo_rastreio,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None

def atualizar_fase_documento(codigo_rastreio: str, fase: str, por_produto: bool = False) -> int:
    """Atualiza fase de um documento. Se por_produto=True, aplica a todos do mesmo produto."""
    conn = get_connection()
    cursor = conn.cursor()

    if por_produto:
        cursor.execute("SELECT produto FROM documentos_impressos WHERE codigo_rastreio = ?", (codigo_rastreio,))
        row = cursor.fetchone()
        if not row:
            conn.close()
            return 0
        produto = row["produto"]
        cursor.execute("UPDATE documentos_impressos SET fase = ? WHERE produto = ?", (fase, produto))
    else:
        cursor.execute("UPDATE documentos_impressos SET fase = ? WHERE codigo_rastreio = ?", (fase, codigo_rastreio))

    affected = cursor.rowcount
    conn.commit()
    conn.close()
    return affected

# Inicializa o banco quando o módulo é importado
init_db()