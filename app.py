
import os
import psycopg
import json
import urllib.request
import urllib.error
import random
import time

from dotenv import load_dotenv
from flask import Flask, request

load_dotenv()

INSTAGRAM_ACCESS_TOKEN = os.getenv('INSTAGRAM_ACCESS_TOKEN')
WEBHOOK_VERIFY_TOKEN = os.getenv('WEBHOOK_VERIFY_TOKEN')

# Palavras-chave que ativam a automação
PALAVRAS_CHAVE = [
    'quero',
    'gostei',
    'quero o link',
    'eu quero',
    'link',
    'me envia',
    'manda o link',
    'me manda',
    'tenho interesse',
    'envia pra mim'
]


# Respostas públicas aleatórias
RESPOSTAS_PUBLICAS = [
    'Oi! 😍 Te enviamos os detalhes pelo Direct!',
    'Olá! ❤️ Dá uma olhadinha na sua caixa de entrada!',
    'Oba! 🥰 Confira seu Direct, enviamos tudo por lá!',
    'Oi! 💕 Acabamos de te enviar uma mensagem!'
]


# Produtos divulgados
PRODUTOS = [
    {
        'nome': 'Climatizador Industrial 70L',
        'link': 'https://link-da-shopee'
    },
    {
        'nome': 'Mini Umificador Portátil',
        'link': 'https://link-do-mercado-livre'
    }
]


# Grupo de ofertas no WhatsApp
LINK_GRUPO_WHATSAPP = 'https://chat.whatsapp.com/SEU-LINK'

DATABASE_URL = os.getenv('DATABASE_URL')


def obter_conexao():
    if not DATABASE_URL:
        raise RuntimeError('DATABASE_URL não configurada.')

    return psycopg.connect(DATABASE_URL)

app = Flask(__name__)

def inicializar_banco():
    with obter_conexao() as conexao:
        conexao.execute('''
            CREATE TABLE IF NOT EXISTS comentarios_processados (
                comment_id TEXT PRIMARY KEY,
                status TEXT NOT NULL
            )
        ''')

        conexao.execute('''
            ALTER TABLE comentarios_processados
            ADD COLUMN IF NOT EXISTS resposta_publica_status TEXT
            NOT NULL DEFAULT 'pendente'
        ''')

        conexao.execute('''
            ALTER TABLE comentarios_processados
            ADD COLUMN IF NOT EXISTS direct_status TEXT
            NOT NULL DEFAULT 'pendente'
        ''')

        conexao.execute('''
            UPDATE comentarios_processados
            SET
                resposta_publica_status = 'enviado',
                direct_status = 'enviado'
            WHERE status = 'enviado'
        ''')


inicializar_banco()



def registrar_comentario(comment_id):
    with obter_conexao() as conexao:
        cursor = conexao.execute(
            '''
            INSERT INTO comentarios_processados
            (
                comment_id,
                status,
                resposta_publica_status,
                direct_status
            )
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (comment_id) DO NOTHING
            RETURNING comment_id
            ''',
            (
                comment_id,
                'processando',
                'pendente',
                'pendente'
            )
        )

        return cursor.fetchone() is not None



def atualizar_status_comentario(comment_id, status):
    with obter_conexao() as conexao:
        conexao.execute(
            '''
            UPDATE comentarios_processados
            SET status = %s
            WHERE comment_id = %s
            ''',
            (status, comment_id)
        )

def atualizar_status_resposta_publica(comment_id, status):
    with obter_conexao() as conexao:
        conexao.execute(
            '''
            UPDATE comentarios_processados
            SET resposta_publica_status = %s
            WHERE comment_id = %s
            ''',
            (status, comment_id)
        )

def atualizar_status_direct(comment_id, status):
    with obter_conexao() as conexao:
        conexao.execute(
            '''
            UPDATE comentarios_processados
            SET direct_status = %s
            WHERE comment_id = %s
            ''',
            (status, comment_id)
        )


def atualizar_status_direct(comment_id, status):
    with obter_conexao() as conexao:
        conexao.execute(
            '''
            UPDATE comentarios_processados
            SET direct_status = %s
            WHERE comment_id = %s
            ''',
            (status, comment_id)
        )


def remover_comentario(comment_id):
    with obter_conexao() as conexao:
        conexao.execute(
            '''
            DELETE FROM comentarios_processados
            WHERE comment_id = %s
            ''',
            (comment_id,)
        )


def responder_comentario_publicamente(comment_id):
    url = f'https://graph.facebook.com/v27.0/{comment_id}/replies'

    mensagem = random.choice(RESPOSTAS_PUBLICAS)

    payload = {
        'message': mensagem
    }

    dados = json.dumps(payload).encode('utf-8')

    requisicao = urllib.request.Request(
        url,
        data=dados,
        headers={
            'Authorization': f'Bearer {INSTAGRAM_ACCESS_TOKEN}',
            'Content-Type': 'application/json'
        },
        method='POST'
    )

    try:
        with urllib.request.urlopen(requisicao) as resposta:
            resultado = json.loads(resposta.read().decode('utf-8'))
            print('Resposta pública enviada com sucesso!')
            print(f'Mensagem: {mensagem}')
            print(f'Retorno da API: {resultado}')
            return True

    except urllib.error.HTTPError as erro:
        detalhes = erro.read().decode('utf-8')
        print(f'Erro ao responder comentário ({erro.code}): {detalhes}')
        return False

    except urllib.error.URLError as erro:
        print(f'Erro de conexão: {erro.reason}')
        return False



def enviar_resposta_privada(instagram_id, comment_id):
    url = f'https://graph.facebook.com/v27.0/{instagram_id}/messages'

    botoes = [
        {
            'type': 'web_url',
            'url': PRODUTOS[0]['link'],
            'title': 'Ver na Shopee'
        },
        {
            'type': 'web_url',
            'url': PRODUTOS[1]['link'],
            'title': 'Ver no Mercado Livre'
        },
        {
            'type': 'web_url',
            'url': LINK_GRUPO_WHATSAPP,
            'title': 'Grupo WhatsApp'
        }
    ]

    mensagem = (
        'Olá! 😊 Que bom que você se interessou!\n\n'
        f'Confira nossos produtos:\n'
        f'• {PRODUTOS[0]["nome"]}\n'
        f'• {PRODUTOS[1]["nome"]}\n\n'
        'Escolha uma das opções abaixo:'
    )

    payload = {
        'recipient': {
            'comment_id': comment_id
        },
        'message': {
            'attachment': {
                'type': 'template',
                'payload': {
                    'template_type': 'button',
                    'text': mensagem,
                    'buttons': botoes
                }
            }
        }
    }

    dados = json.dumps(payload).encode('utf-8')

    requisicao = urllib.request.Request(
        url,
        data=dados,
        headers={
            'Authorization': f'Bearer {INSTAGRAM_ACCESS_TOKEN}',
            'Content-Type': 'application/json'
        },
        method='POST'
    )

    try:
        with urllib.request.urlopen(requisicao) as resposta:
            resultado = json.loads(resposta.read().decode('utf-8'))
            print('Resposta privada enviada com sucesso!')
            print(f'Retorno da API: {resultado}')
            return True

    except urllib.error.HTTPError as erro:
        detalhes = erro.read().decode('utf-8')
        print(f'Erro da API ({erro.code}): {detalhes}')
        return False

    except urllib.error.URLError as erro:
        print(f'Erro de conexão: {erro.reason}')
        return False


@app.route('/')
def home():
    return 'Instagram Auto DM - Sistema funcionando!'


@app.route('/auth/instagram/callback')
def instagram_callback():
    code = request.args.get('code')
    error = request.args.get('error')

    if error:
        return f'Erro na autorização: {error}'

    if not code:
        return 'Código de autorização não recebido.', 400

    return f'Código de autorização recebido: {code}'


@app.route('/webhook', methods=['GET'])
def webhook_verification():
    verify_token = request.args.get('hub.verify_token')
    challenge = request.args.get('hub.challenge')
    mode = request.args.get('hub.mode')

    if mode == 'subscribe' and verify_token == WEBHOOK_VERIFY_TOKEN:
        return challenge, 200

    return 'Token de verificação inválido', 403


@app.route('/webhook', methods=['POST'])
def webhook_receive():
    data = request.get_json(silent=True)

    if not data:
        return 'Dados inválidos', 400

    print('\n===== WEBHOOK RECEBIDO =====')

    for entry in data.get('entry', []):
        instagram_id = entry.get('id')

        for change in entry.get('changes', []):
            if change.get('field') == 'comments':
                comment = change.get('value', {})

                comment_id = comment.get('comment_id') or comment.get('id')
                comment_text = comment.get('text')
                media = comment.get('media', {})
                media_id = media.get('id')
                user = comment.get('from', {})
                username = user.get('username')

                print(f'Conta Instagram: {instagram_id}')
                print(f'ID do comentário: {comment_id}')
                print(f'Usuário: {username}')
                print(f'Comentário: {comment_text}')
                print(f'ID da publicação: {media_id}')

                if comment_text and comment_text.strip().casefold() in PALAVRAS_CHAVE:
                    print('PALAVRA-CHAVE IDENTIFICADA!')

                    if not instagram_id or not comment_id:
                        print('Dados insuficientes para processar o comentário.')
                        continue

                    if not registrar_comentario(comment_id):
                        print('Comentário já processado. Nenhuma ação será repetida.')
                        continue

                    # Tenta responder publicamente
                    sucesso_publico = responder_comentario_publicamente(comment_id)

                    if sucesso_publico:
                        atualizar_status_resposta_publica(comment_id, 'enviado')
                    else:
                        atualizar_status_resposta_publica(comment_id, 'erro')
                        print('Falha na resposta pública. O Direct será tentado mesmo assim.')

                    # Tenta enviar o Direct até 3 vezes
                    sucesso_direct = False

                    for tentativa in range(1, 4):
                        print(f'Tentativa {tentativa} de envio do Direct.')

                        sucesso_direct = enviar_resposta_privada(instagram_id, comment_id)

                        if sucesso_direct:
                            atualizar_status_direct(comment_id, 'enviado')
                            print('Direct enviado com sucesso!')
                            break

                        if tentativa < 3:
                            print('Falha no envio. Nova tentativa em 2 segundos.')
                            time.sleep(2)

                    if sucesso_direct:
                        atualizar_status_comentario(comment_id, 'concluido')
                    else:
                        atualizar_status_direct(comment_id, 'erro')
                        atualizar_status_comentario(comment_id, 'erro')
                        print('As três tentativas falharam. Registro mantido no banco.')

                else:
                    print('Palavra-chave não identificada.')

        print('============================\n')

    return 'EVENT_RECEIVED', 200



if __name__ == '__main__':
    app.run(debug=True)
