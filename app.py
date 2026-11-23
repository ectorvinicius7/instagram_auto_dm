
import os
import json
import urllib.request
import urllib.error

from dotenv import load_dotenv
from flask import Flask, request

load_dotenv()

INSTAGRAM_ACCESS_TOKEN = os.getenv('INSTAGRAM_ACCESS_TOKEN')
WEBHOOK_VERIFY_TOKEN = os.getenv('WEBHOOK_VERIFY_TOKEN')

app = Flask(__name__)

def enviar_resposta_privada(instagram_id, comment_id, mensagem):
    url = f'https://graph.facebook.com/v27.0/{instagram_id}/messages'

    payload = {
        'recipient': {
            'comment_id': comment_id
        },
        'message': {
            'text': mensagem
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

                # Verifica a palavra-chave
                if comment_text and comment_text.strip().casefold() == 'quero':
                    print('PALAVRA-CHAVE IDENTIFICADA!')
                else:
                    print('Palavra-chave não identificada.')

    print('============================\n')

    return 'EVENT_RECEIVED', 200


if __name__ == '__main__':
    app.run(debug=True)
