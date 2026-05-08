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
            role TEXT NOT NULL DEFAULT 'user',
            ativo INTEGER DEFAULT 1,
            criado_em TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
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
    
    # Migrations para colunas adicionadas ao longo do tempo
    migrations = [
        "ALTER TABLE documentos_impressos ADD COLUMN fase TEXT DEFAULT NULL",
        "ALTER TABLE usuarios ADD COLUMN role TEXT DEFAULT 'user'",
        "ALTER TABLE usuarios ADD COLUMN updated_at TEXT DEFAULT CURRENT_TIMESTAMP",
    ]
    for sql in migrations:
        try:
            cursor.execute(sql)
            conn.commit()
        except sqlite3.OperationalError:
            pass

    # Tabela de tokens de reset de senha
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS password_reset_tokens (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL REFERENCES usuarios(id) ON DELETE CASCADE,
            token TEXT UNIQUE NOT NULL,
            expires_at TEXT NOT NULL,
            used_at TEXT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

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
        "SELECT id, nome, usuario, senha_hash, ativo, role FROM usuarios WHERE usuario = ?",
        (usuario,)
    )
    row = cursor.fetchone()
    conn.close()

    if row and row["ativo"] and check_password_hash(row["senha_hash"], senha):
        return {"id": row["id"], "nome": row["nome"], "usuario": row["usuario"], "role": row["role"] or "user"}
    return None

def listar_usuarios():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, nome, usuario, role, ativo, criado_em FROM usuarios ORDER BY criado_em DESC")
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

def get_usuario(user_id: int) -> dict | None:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id, nome, usuario, role, ativo, criado_em, updated_at FROM usuarios WHERE id = ?",
        (user_id,)
    )
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None

def criar_usuario_admin(nome: str, usuario: str, senha: str, role: str = "user") -> dict | None:
    try:
        conn = get_connection()
        cursor = conn.cursor()
        senha_hash = generate_password_hash(senha)
        cursor.execute(
            "INSERT INTO usuarios (nome, usuario, senha_hash, role) VALUES (?, ?, ?, ?)",
            (nome, usuario, senha_hash, role)
        )
        user_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return get_usuario(user_id)
    except sqlite3.IntegrityError:
        return None

def atualizar_usuario(user_id: int, nome: str = None, role: str = None, ativo: int = None) -> bool:
    fields, values = [], []
    if nome is not None:
        fields.append("nome = ?"); values.append(nome)
    if role is not None:
        fields.append("role = ?"); values.append(role)
    if ativo is not None:
        fields.append("ativo = ?"); values.append(ativo)
    if not fields:
        return False
    fields.append("updated_at = ?"); values.append(datetime.now().isoformat())
    values.append(user_id)
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(f"UPDATE usuarios SET {', '.join(fields)} WHERE id = ?", values)
    affected = cursor.rowcount
    conn.commit()
    conn.close()
    return affected > 0

def contar_admins_ativos() -> int:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM usuarios WHERE role = 'admin' AND ativo = 1")
    count = cursor.fetchone()[0]
    conn.close()
    return count

def gerar_token_reset(user_id: int, token: str, expires_at: str):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO password_reset_tokens (user_id, token, expires_at) VALUES (?, ?, ?)",
        (user_id, token, expires_at)
    )
    conn.commit()
    conn.close()

def get_token_reset(token: str) -> dict | None:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT t.*, u.usuario, u.nome
        FROM password_reset_tokens t
        JOIN usuarios u ON t.user_id = u.id
        WHERE t.token = ?
    """, (token,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None

def usar_token_reset(token: str, nova_senha_hash: str) -> bool:
    conn = get_connection()
    cursor = conn.cursor()
    agora = datetime.now().isoformat()
    cursor.execute(
        "SELECT user_id FROM password_reset_tokens WHERE token = ? AND used_at IS NULL",
        (token,)
    )
    row = cursor.fetchone()
    if not row:
        conn.close()
        return False
    user_id = row["user_id"]
    cursor.execute("UPDATE password_reset_tokens SET used_at = ? WHERE token = ?", (agora, token))
    cursor.execute("UPDATE usuarios SET senha_hash = ?, updated_at = ? WHERE id = ?", (nova_senha_hash, agora, user_id))
    conn.commit()
    conn.close()
    return True

def registrar_log_auditoria(acao: str, user_id: int, target_id: int = None, detalhes: str = None):
    print(f"[AUDIT] {datetime.now().isoformat()} | user={user_id} | acao={acao} | target={target_id} | {detalhes or ''}")

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
    usuario_id: int,
    fase: str = None
):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO documentos_impressos
        (codigo_rastreio, produto, arquivo, pasta, impressora, computador, impresso_por_id, fase)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (codigo_rastreio, produto, arquivo, pasta, impressora, computador, usuario_id, fase))
    conn.commit()
    conn.close()

def listar_documentos(status: str = None, limite: int = 2000):
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