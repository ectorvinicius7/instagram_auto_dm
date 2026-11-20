
import os
from dotenv import load_dotenv
from flask import Flask, request

load_dotenv()

INSTAGRAM_ACCESS_TOKEN = os.getenv('INSTAGRAM_ACCESS_TOKEN')
WEBHOOK_VERIFY_TOKEN = os.getenv('WEBHOOK_VERIFY_TOKEN')

app = Flask(__name__)


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

                comment_id = comment.get('id')
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
