# Operação e deploy em produção

## Visão geral

O FastPrint de produção está hospedado em uma VM Linux e executado como serviço systemd.

| Item | Configuração |
|---|---|
| Servidor | **192.168.1.171** |
| Hostname | **5026145** |
| Diretório | **/root/printfast** |
| Branch de produção | **cups-logs** |
| Ambiente virtual | **/root/printfast/venv** |
| Serviço | **fastprint.service** |
| Aplicação ASGI | **main:app** |
| Porta | **8081** |
| URL interna | **http://192.168.1.171:8081** |
| Ambiente | **FASTPRINT_ENV=production** |
| Banco | **/root/printfast/fastprint.db** |

A porta 8080 pertence a outra aplicação no servidor. O FastPrint deve continuar usando a porta 8081.

## Serviço systemd

Arquivo: **/etc/systemd/system/fastprint.service**

~~~ini
[Unit]
Description=FastPrint - Linea Brasil
After=network-online.target
Wants=network-online.target

[Service]
User=root
WorkingDirectory=/root/printfast
ExecStart=/root/printfast/venv/bin/uvicorn main:app --host 0.0.0.0 --port 8081
Restart=always
RestartSec=5
Environment=FASTPRINT_ENV=production

[Install]
WantedBy=multi-user.target
~~~

O serviço inicia com o sistema e reinicia automaticamente após falhas.

### Comandos operacionais

~~~bash
systemctl status fastprint.service --no-pager -l
systemctl start fastprint.service
systemctl stop fastprint.service
systemctl restart fastprint.service
journalctl -u fastprint.service -n 100 --no-pager
journalctl -u fastprint.service -f
~~~

## Compartilhamento de documentos

~~~text
Origem:  //192.168.1.250/xeon
Destino: /mnt/xeon
Tipo:    CIFS 3.0
Modo:    somente leitura
~~~

Entrada correspondente em **/etc/fstab**:

~~~fstab
//192.168.1.250/xeon /mnt/xeon cifs credentials=/root/.smbcredentials,vers=3.0,ro,_netdev,nofail,iocharset=utf8,file_mode=0444,dir_mode=0555 0 0
~~~

O processo FastPrint roda localmente como root. A autenticação SMB usa
**/root/.smbcredentials**. O conteúdo desse arquivo nunca deve ser colocado no
Git, nos logs ou nesta documentação.

Verificação:

~~~bash
findmnt -T /mnt/xeon
ls "/mnt/xeon/Linea Brasil" >/dev/null && echo "Compartilhamento OK"
~~~

Se necessário:

~~~bash
mount /mnt/xeon
~~~

## Banco de dados

O banco operacional é **/root/printfast/fastprint.db**. Ele está no
.gitignore e não é distribuído pelo Git. Um clone novo cria um banco vazio na
primeira inicialização; o banco de produção deve sempre ser preservado.

Backup manual com o serviço parado:

~~~bash
systemctl stop fastprint.service
mkdir -p /root/printfast-backups
cp -p /root/printfast/fastprint.db   /root/printfast-backups/fastprint-$(date +%Y%m%d-%H%M%S).db
ls -lh /root/printfast-backups/
~~~

## Procedimento de deploy

### 1. Verificar a worktree

~~~bash
cd /root/printfast
git status --short --branch
~~~

Não continuar se houver alterações locais em código sem antes analisá-las.

### 2. Parar e salvar o banco

~~~bash
systemctl stop fastprint.service
mkdir -p /root/printfast-backups
cp -p fastprint.db   /root/printfast-backups/fastprint-$(date +%Y%m%d-%H%M%S).db
~~~

### 3. Atualizar o código

~~~bash
git checkout cups-logs
git pull --ff-only origin cups-logs
~~~

### 4. Atualizar dependências

~~~bash
source /root/printfast/venv/bin/activate
python -m pip install -r requirements.txt
python -m pip install pypdf reportlab
python -c "import fastapi, cups, pypdf, reportlab; print('Dependências OK')"
~~~

### 5. Verificar recursos e iniciar

~~~bash
test -f /root/printfast/fastprint.db
findmnt -T /mnt/xeon
ls "/mnt/xeon/Linea Brasil" >/dev/null
systemctl start fastprint.service
~~~

### 6. Validar

~~~bash
systemctl status fastprint.service --no-pager -l
curl -s http://127.0.0.1:8081/api/dashboard
journalctl -u fastprint.service --since "5 minutes ago" --no-pager
~~~

O deploy está saudável quando o serviço está ativo, a API responde HTTP 200,
não há exceções recentes e /mnt/xeon permanece acessível.

## Teste funcional

1. Atualizar o navegador com Ctrl + F5.
2. Colar um caminho até 07 - DOCUMENTOS TECNICOS.
3. Clicar em **Escanear**.
4. Conferir Furação, Grampeação e Usinagem.
5. Imprimir apenas um PDF.
6. Conferir Rastreio e Dashboard.
7. Confirmar que o mesmo scan_id não pode ser reutilizado.

## Limites operacionais

- até 100 PDFs por operação;
- uma impressão ativa por processo;
- scan_id válido por 10 minutos e de uso único;
- 10 varreduras por minuto por IP;
- 5 solicitações de impressão por minuto por IP;
- 30 buscas ou navegações por minuto por IP.

## Diagnóstico rápido

~~~bash
systemctl is-enabled fastprint.service
systemctl is-active fastprint.service
ss -ltnp | grep ':8081'
findmnt -T /mnt/xeon
curl -s -o /dev/null -w '%{http_code}\n' \
  http://127.0.0.1:8081/api/dashboard
~~~

Resultado esperado: serviço enabled, active e resposta HTTP 200.
