# 🖨️ PrintHub - Sistema de Impressão em Lote

> Operação do servidor, deploy e diagnóstico: [docs/DEPLOY_PRODUCAO.md](docs/DEPLOY_PRODUCAO.md)

Sistema para impressão automática de documentos PDF de produtos - Linea Brasil.

## 🚀 Instalação Rápida

### Windows (Recomendado para Fase 1)

1. **Instale Python 3.10+** se ainda não tiver:
   - Baixe em: https://www.python.org/downloads/
   - ✅ Marque "Add Python to PATH" durante instalação

2. **Abra o Prompt de Comando** na pasta do projeto:
   ```cmd
   cd C:\caminho\para\print-system
   ```

3. **Instale as dependências:**
   ```cmd
   pip install -r requirements.txt
   pip install pywin32
   ```

4. **Execute o sistema:**
   ```cmd
   python main.py
   ```

5. **Acesse no navegador:**
   ```
   http://localhost:8000
   ```

---

## 📖 Como Usar

1. Cole o caminho completo da pasta do produto
   - Exemplo: `L:\Linea Brasil\...\810015103 - AEREO 1.2M BLESS`

2. Clique em **"Escanear"**
   - O sistema vai encontrar todos os PDFs nas pastas que começam com "ENG"

3. Selecione a impressora desejada

4. Clique em **"Imprimir Tudo"**
   - Todos os PDFs serão enviados para a impressora

---

## ⚙️ Configuração

Edite o arquivo `main.py` para ajustar:

```python
# Caminho base dos produtos
BASE_PATH = r"L:\Linea Brasil\6 Pesquisa e Desenvolvimento\..."

# Impressora padrão (deixe None para usar a do sistema)
DEFAULT_PRINTER = None  # ou "Nome da Impressora"
```

---

## 🔐 Variáveis de Ambiente

| Variável | Padrão | Descrição |
|---|---|---|
| `FASTPRINT_ENV` | `production` | Modo de execução. Use `development` apenas em dev local. |

**Em desenvolvimento local**, setar antes de rodar o servidor habilita o bypass de autenticação com o token `"temp"` (permite testar sem login real):

```cmd
set FASTPRINT_ENV=development
python main.py
```

Ou via PowerShell:

```powershell
$env:FASTPRINT_ENV = "development"
python main.py
```

**Em produção (NSSM)**, esta variável **não deve estar definida**. Serviços Windows via NSSM não herdam variáveis de ambiente do usuário — só enxergam variáveis de sistema ou o que for explicitamente configurado na aba "Environment" do `nssm edit fastprint`. Para confirmar que está limpo no servidor:

```cmd
nssm edit fastprint
```

Na aba **"Environment"**, verificar que `FASTPRINT_ENV` não aparece. Se aparecer, remover.

---

## 🌐 Abrindo para a Equipe (Fase 2)

Para permitir que outros acessem:

1. **Descubra seu IP local:**
   ```cmd
   ipconfig
   ```
   Procure por "Endereço IPv4" (ex: 192.168.1.50)

2. **Libere no Firewall do Windows:**
   - Painel de Controle > Firewall > Configurações Avançadas
   - Nova Regra de Entrada > Porta > TCP 8000 > Permitir

3. **Outros acessam via:**
   ```
   http://IP:8000
   ```

---

## 🔧 Troubleshooting

### Erro: "Pasta não encontrada"
- Verifique se a unidade L: está mapeada
- Verifique se você tem acesso à pasta

### Erro: "Impressora não encontrada"
- Verifique se a impressora está instalada no Windows
- Tente usar "Impressora Padrão do Sistema"

### PDFs não imprimem
- Instale o `pywin32`: `pip install pywin32`
- Verifique se tem um leitor de PDF instalado (Adobe, Foxit, etc.)

---

## 📁 Estrutura de Pastas Esperada

```
810015103 - AEREO 1.2M BLESS/
├── ENG-DESENHOS/
│   ├── desenho1.pdf  ✅ Será impresso
│   └── desenho2.pdf  ✅ Será impresso
├── ENG-ESPECIFICACOES/
│   └── specs.pdf     ✅ Será impresso
├── OUTROS/
│   └── arquivo.pdf   ❌ Ignorado (não começa com ENG)
└── readme.txt        ❌ Ignorado (não é PDF)
```

Desenvolvido para Linea Brasil 🏭
