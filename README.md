# 🖨️ PrintHub - Sistema de Impressão em Lote

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
   http://192.168.1.50:8000
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

---

## 🚧 Roadmap

- [x] Fase 1: Interface web local
- [x] Fase 2: Login e controle de acesso
- [x] Fase 3: Histórico de impressões
- [ ] Fase 4: Integração com ciclo de vida do produto

---

Desenvolvido para Linea Brasil 🏭
