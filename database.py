"""
Banco de Dados - FastPrint

Módulo responsável por toda a persistência de dados da aplicação.
Gerencia:
  - Usuários e autenticação (login, criação, ativação/desativação)
  - Logs de impressão (histórico de operações)
  - Rastreio de documentos impressos (código de rastreio, status, fase)
  - Tokens de reset de senha

Utiliza SQLite como banco de dados local (arquivo fastprint.db).
"""

import sqlite3
import logging
from pathlib import Path
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash

# Configuração do logger para o módulo de banco de dados
logger = logging.getLogger(__name__)

# Caminho do arquivo do banco de dados SQLite (na mesma pasta do script)
DB_PATH = Path(__file__).parent / "fastprint.db"

def get_connection():
    """Retorna conexão com o banco SQLite com suporte a acesso por nome de coluna."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row  # Permite acessar colunas pelo nome (ex: row["id"])
    return conn

def init_db():
    """Cria as tabelas do banco se ainda não existirem. Executado na inicialização."""
    logger.info(f"Inicializando banco de dados: {DB_PATH}")
    conn = get_connection()
    cursor = conn.cursor()
    
    # Tabela de usuários do sistema (login e permissões)
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
    
    # Tabela de logs de impressão (histórico geral, mantida para compatibilidade)
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

    # Tabela principal de rastreio: cada PDF impresso recebe um registro
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

    # Contador sequencial diário para geração de códigos de rastreio únicos
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS contador_rastreio (
            data TEXT PRIMARY KEY,
            contador INTEGER DEFAULT 0
        )
    """)
    
    # Migrations: adiciona colunas que foram incluídas após a criação inicial do banco
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

    # Tabela de tokens para recuperação de senha (expiráveis e de uso único)
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
    logger.info("Banco de dados inicializado com sucesso")

# ============================================
# USUÁRIOS
# Funções para gerenciamento de usuários:
# criação, login, listagem, ativação/desativação
# e atualização de dados.
# ============================================

def criar_usuario(nome: str, usuario: str, senha: str) -> bool:
    """Cria um novo usuário com senha criptografada. Retorna False se o usuário já existir."""
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
        logger.info(f"Usuário criado: {usuario}")
        return True
    except sqlite3.IntegrityError:
        logger.warning(f"Tentativa de criar usuário duplicado: {usuario}")
        return False

def verificar_login(usuario: str, senha: str) -> dict | None:
    """Verifica credenciais de login. Retorna dados do usuário ou None se inválido."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id, nome, usuario, senha_hash, ativo, role FROM usuarios WHERE usuario = ?",
        (usuario,)
    )
    row = cursor.fetchone()
    conn.close()

    if row and row["ativo"] and check_password_hash(row["senha_hash"], senha):
        logger.info(f"Login bem-sucedido: {usuario}")
        return {"id": row["id"], "nome": row["nome"], "usuario": row["usuario"], "role": row["role"] or "user"}
    logger.warning(f"Tentativa de login falhou para usuário: {usuario}")
    return None

def listar_usuarios():
    """Retorna lista de todos os usuários cadastrados, ordenados por data de criação."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, nome, usuario, role, ativo, criado_em FROM usuarios ORDER BY criado_em DESC")
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]

def desativar_usuario(usuario_id: int):
    """Desativa um usuário (soft delete), impedindo-o de fazer login."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE usuarios SET ativo = 0 WHERE id = ?", (usuario_id,))
    conn.commit()
    conn.close()
    logger.info(f"Usuário desativado: ID {usuario_id}")

def ativar_usuario(usuario_id: int):
    """Reativa um usuário previamente desativado."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE usuarios SET ativo = 1 WHERE id = ?", (usuario_id,))
    conn.commit()
    conn.close()
    logger.info(f"Usuário reativado: ID {usuario_id}")

def get_usuario(user_id: int) -> dict | None:
    """Busca um usuário pelo ID. Retorna dict com dados ou None."""
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
    """Cria usuário com role específica (admin ou user). Usado pela administração."""
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
        logger.info(f"Usuário admin criado: {usuario} (role={role})")
        return get_usuario(user_id)
    except sqlite3.IntegrityError:
        logger.warning(f"Tentativa de criar usuário admin duplicado: {usuario}")
        return None

def atualizar_usuario(user_id: int, nome: str = None, role: str = None, ativo: int = None) -> bool:
    """Atualiza campos de um usuário. Apenas os parâmetros informados são alterados."""
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
    logger.info(f"Usuário atualizado: ID {user_id} | Campos: {fields}")
    return affected > 0

def contar_admins_ativos() -> int:
    """Conta quantos administradores ativos existem no sistema."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM usuarios WHERE role = 'admin' AND ativo = 1")
    count = cursor.fetchone()[0]
    conn.close()
    return count

def gerar_token_reset(user_id: int, token: str, expires_at: str):
    """Cria um token de recuperação de senha para o usuário."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO password_reset_tokens (user_id, token, expires_at) VALUES (?, ?, ?)",
        (user_id, token, expires_at)
    )
    conn.commit()
    conn.close()
    logger.info(f"Token de reset gerado para usuário ID {user_id}")

def get_token_reset(token: str) -> dict | None:
    """Busca um token de reset e retorna dados do token e do usuário associado."""
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
    """Utiliza um token de reset para alterar a senha do usuário. Marca o token como usado."""
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
    logger.info(f"Senha redefinida via token para usuário ID {user_id}")
    return True

def registrar_log_auditoria(acao: str, user_id: int, target_id: int = None, detalhes: str = None):
    """Registra ações administrativas para auditoria (impresso no console)."""
    logger.info(f"[AUDIT] user={user_id} | acao={acao} | target={target_id} | {detalhes or ''}")

# ============================================
# LOGS (compatibilidade)
# Histórico geral de operações de impressão.
# Mantido para compatibilidade com versões anteriores.
# ============================================

def registrar_log(usuario_id: int, produto: str, pasta: str, arquivos: list, impressora: str):
    """Registra um log de impressão no banco com produto, arquivos e impressora utilizada."""
    logger.info(f"Registrando log: produto='{produto}', {len(arquivos)} arquivo(s), impressora='{impressora}'")
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
    """Retorna os últimos logs de impressão com nome do usuário associado."""
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
# Sistema de rastreio individual de cada PDF impresso.
# Cada documento recebe um código único (FP-DATA-SEQ-PC)
# e pode ter seu status atualizado (entregue → baixado)
# e sua fase de produção definida.
# ============================================

def gerar_codigo_rastreio(computador: str) -> str:
    """Gera código de rastreio único no formato: FP-AAAAMMDD-SEQ-PC (sequencial diário)."""
    hoje = datetime.now().strftime("%Y%m%d")
    conn = get_connection()
    cursor = conn.cursor()
    
    # Incrementa o contador do dia atual
    cursor.execute("INSERT OR IGNORE INTO contador_rastreio (data, contador) VALUES (?, 0)", (hoje,))
    cursor.execute("UPDATE contador_rastreio SET contador = contador + 1 WHERE data = ?", (hoje,))
    cursor.execute("SELECT contador FROM contador_rastreio WHERE data = ?", (hoje,))
    seq = cursor.fetchone()["contador"]
    conn.commit()
    conn.close()
    
    # Limita e limpa o nome do computador (só alfanuméricos, máx 8 chars)
    pc = "".join(c for c in computador.upper() if c.isalnum())[:8]
    codigo = f"FP-{hoje}-{seq:04d}-{pc}"
    logger.info(f"Código de rastreio gerado: {codigo}")
    return codigo

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
    """Registra um documento impresso no banco para rastreio. Cada PDF tem seu próprio registro."""
    logger.info(f"Registrando documento: {codigo_rastreio} | arquivo='{arquivo}' | produto='{produto}'")
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
    """Lista documentos impressos com dados dos usuários responsáveis (quem imprimiu, recolheu, baixou)."""
    conn = get_connection()
    cursor = conn.cursor()
    
    query = """
        SELECT
            d.*,
            u1.nome as impresso_por_nome,
            u2.nome as recolhido_por_nome,
            u3.nome as baixado_por_nome
        FROM documentos_impressos d
        LEFT JOIN usuarios u1 ON d.impresso_por_id = u1.id
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
    """Atualiza o status de um documento. Transição permitida: entregue → baixado."""
    logger.info(f"Atualizando status: {codigo_rastreio} → '{novo_status}' (usuário ID {usuario_id})")
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
    """Busca um documento específico pelo código de rastreio, incluindo dados dos usuários."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT 
            d.*,
            u1.nome as impresso_por_nome,
            u2.nome as recolhido_por_nome,
            u3.nome as baixado_por_nome
        FROM documentos_impressos d
        LEFT JOIN usuarios u1 ON d.impresso_por_id = u1.id
        LEFT JOIN usuarios u2 ON d.recolhido_por_id = u2.id
        LEFT JOIN usuarios u3 ON d.baixado_por_id = u3.id
        WHERE d.codigo_rastreio = ?
    """, (codigo_rastreio,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None

def atualizar_fase_documento(codigo_rastreio: str, fase: str, por_produto: bool = False) -> int:
    """Atualiza a fase de produção de um documento. Se por_produto=True, aplica a todos os documentos do mesmo produto."""
    logger.info(f"Atualizando fase: {codigo_rastreio} → '{fase}' (por_produto={por_produto})")
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

def obter_metricas_dashboard() -> dict:
    """Retorna métricas agregadas de todo o histórico para o Dashboard."""
    conn = get_connection()
    cursor = conn.cursor()

    resumo = dict(cursor.execute("""
        SELECT
            COUNT(*) AS total,
            SUM(CASE WHEN status = 'entregue' THEN 1 ELSE 0 END) AS entregues,
            SUM(CASE WHEN status = 'baixado' THEN 1 ELSE 0 END) AS baixados,
            SUM(CASE WHEN fase IS NULL OR TRIM(fase) = '' THEN 1 ELSE 0 END) AS sem_fase,
            MIN(impresso_em) AS inicio,
            MAX(impresso_em) AS fim
        FROM documentos_impressos
    """).fetchone())

    fases = {
        row["fase"]: row["total"]
        for row in cursor.execute("""
            SELECT COALESCE(NULLIF(TRIM(fase), ''), 'Sem fase') AS fase, COUNT(*) AS total
            FROM documentos_impressos
            GROUP BY COALESCE(NULLIF(TRIM(fase), ''), 'Sem fase')
        """).fetchall()
    }

    top_produtos = [
        dict(row) for row in cursor.execute("""
            SELECT
                produto,
                COUNT(*) AS total,
                SUM(CASE WHEN status = 'entregue' THEN 1 ELSE 0 END) AS entregues,
                SUM(CASE WHEN status = 'baixado' THEN 1 ELSE 0 END) AS baixados
            FROM documentos_impressos
            GROUP BY produto
            ORDER BY total DESC, produto
            LIMIT 10
        """).fetchall()
    ]

    computadores = [
        dict(row) for row in cursor.execute("""
            SELECT COALESCE(NULLIF(TRIM(computador), ''), 'Desconhecido') AS computador,
                   COUNT(*) AS total
            FROM documentos_impressos
            GROUP BY COALESCE(NULLIF(TRIM(computador), ''), 'Desconhecido')
            ORDER BY total DESC, computador
            LIMIT 8
        """).fetchall()
    ]

    recentes = [
        dict(row) for row in cursor.execute("""
            SELECT produto, arquivo, impresso_em, status
            FROM documentos_impressos
            ORDER BY impresso_em DESC, id DESC
            LIMIT 10
        """).fetchall()
    ]
    conn.close()

    total = resumo["total"] or 0
    baixados = resumo["baixados"] or 0
    return {
        "resumo": {
            "total": total,
            "entregues": resumo["entregues"] or 0,
            "baixados": baixados,
            "sem_fase": resumo["sem_fase"] or 0,
            "taxa_baixa": round((baixados / total) * 100, 1) if total else 0.0,
        },
        "fases": fases,
        "top_produtos": top_produtos,
        "computadores": computadores,
        "recentes": recentes,
        "periodo": {"inicio": resumo["inicio"], "fim": resumo["fim"]},
    }


def get_or_create_sistema_user() -> int:
    """Retorna o ID do usuário 'sistema'. Cria automaticamente se não existir (usuário padrão do app)."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM usuarios WHERE usuario = 'sistema'")
    row = cursor.fetchone()
    if row:
        conn.close()
        return row["id"]
    cursor.execute(
        "INSERT INTO usuarios (nome, usuario, senha_hash, role) VALUES ('Sistema', 'sistema', '', 'user')"
    )
    user_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return user_id

# Inicializa o banco de dados automaticamente quando o módulo é importado
init_db()