"""
Banco de Dados
Gerencia usuários e logs de impressão
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
    
    # Tabela de logs
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
    
    conn.commit()
    conn.close()

def criar_usuario(nome: str, usuario: str, senha: str) -> bool:
    """Cria um novo usuário"""
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
        return False  # Usuário já existe

def verificar_login(usuario: str, senha: str) -> dict | None:
    """Verifica login e retorna dados do usuário ou None"""
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

def registrar_log(usuario_id: int, produto: str, pasta: str, arquivos: list, impressora: str):
    """Registra uma impressão no log"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """INSERT INTO logs (usuario_id, produto, pasta, arquivos, quantidade, impressora) 
           VALUES (?, ?, ?, ?, ?, ?)""",
        (usuario_id, produto, pasta, ",".join(arquivos), len(arquivos), impressora)
    )
    conn.commit()
    conn.close()

def listar_usuarios():
    """Lista todos os usuários"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, nome, usuario, ativo, criado_em FROM usuarios")
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]

def listar_logs(limite: int = 100):
    """Lista os últimos logs"""
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

def desativar_usuario(usuario_id: int):
    """Desativa um usuário"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE usuarios SET ativo = 0 WHERE id = ?", (usuario_id,))
    conn.commit()
    conn.close()

def ativar_usuario(usuario_id: int):
    """Ativa um usuário"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE usuarios SET ativo = 1 WHERE id = ?", (usuario_id,))
    conn.commit()
    conn.close()

# Inicializa o banco quando o módulo é importado
init_db()