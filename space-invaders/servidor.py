import socket
import threading
import json
import time
import random
from concurrent.futures import ThreadPoolExecutor

HOST = '0.0.0.0'
PORTA = 5555
FPS = 30
TICK = 1 / FPS
LARGURA, ALTURA = 640, 600
LINHAS_INIMIGOS, COLUNAS_INIMIGOS = 2, 6
ESPACO_X_INIMIGO, ESPACO_Y_INIMIGO = 50, 40
INICIO_X_INIMIGO, INICIO_Y_INIMIGO = 20, 20
LARGURA_INIMIGO, ALTURA_INIMIGO = 30, 30
VEL_BALA = 5
VEL_BALA_INIMIGA = 4
COOLDOWN = 0.5  # segundos
DURACAO_IMUNIDADE = 2  # segundos
LIMITE_VERTICAL = ALTURA - 50

clientes = {}
trava = threading.Lock()

# Inicializar estado do jogo
estado_jogo = {
    'pronto': {'atirador': False, 'inimigo': False},
    'iniciado': False,
    'atirador': {
        'x': LARGURA // 2,
        'y': ALTURA - 50,
        'balas': [],
        'ultimo_tiro': 0,
        'vidas': 3,
        'imune_ate': 0
    },
    'inimigos': [],
    'direcao_inimigo': 1,
    'velocidade_inimigo': 0.5,
    'balas_inimigas': [],
    'fim_jogo': False,
    'vencedor': None
}

# Preencher grade de inimigos
for linha in range(LINHAS_INIMIGOS):
    for coluna in range(COLUNAS_INIMIGOS):
        x = INICIO_X_INIMIGO + coluna * ESPACO_X_INIMIGO
        y = INICIO_Y_INIMIGO + linha * ESPACO_Y_INIMIGO
        estado_jogo['inimigos'].append({'x': x, 'y': y})


def lidar_cliente(conn, tipo_jogador):
    with conn:
        while True:
            try:
                dados = conn.recv(1024)
                if not dados:
                    break
                msg = json.loads(dados.decode())
                with trava:
                    if msg['type'] == 'input':
                        acao = msg['action']
                        if acao == 'pronto':
                            estado_jogo['pronto'][tipo_jogador] = True
                        elif estado_jogo['iniciado'] and not estado_jogo['fim_jogo']:
                            if tipo_jogador == 'atirador':
                                if acao in ('esquerda', 'direita'):
                                    dx = -10 if acao == 'esquerda' else 10
                                    estado_jogo['atirador']['x'] = max(0, min(LARGURA-40, estado_jogo['atirador']['x'] + dx))
                                elif acao == 'atirar':
                                    agora = time.time()
                                    if agora - estado_jogo['atirador']['ultimo_tiro'] >= COOLDOWN:
                                        sx = estado_jogo['atirador']['x'] + 18
                                        sy = estado_jogo['atirador']['y']
                                        estado_jogo['atirador']['balas'].append({'x': sx, 'y': sy})
                                        estado_jogo['atirador']['ultimo_tiro'] = agora
                            elif tipo_jogador == 'inimigo':
                                if acao in ('esquerda', 'direita'):
                                    dx = -10 if acao == 'esquerda' else 10
                                    # só move se todos os inimigos ficarem dentro dos limites
                                    if all(0 <= e['x'] + dx <= LARGURA-LARGURA_INIMIGO for e in estado_jogo['inimigos']):
                                        for e in estado_jogo['inimigos']:
                                            e['x'] += dx
                                elif acao == 'atirar':
                                    # agenda bala inimiga de inimigo aleatório
                                    if estado_jogo['inimigos']:
                                        atirador = random.choice(estado_jogo['inimigos'])
                                        bx = atirador['x'] + LARGURA_INIMIGO//2
                                        by = atirador['y'] + ALTURA_INIMIGO
                                        estado_jogo['balas_inimigas'].append({'x': bx, 'y': by})
            except Exception:
                break


def esperar_inicio():
    # Espera até ambos jogadores prontos
    while True:
        time.sleep(0.1)
        with trava:
            if estado_jogo['pronto']['atirador'] and estado_jogo['pronto']['inimigo']:
                estado_jogo['iniciado'] = True
                # Notifica clientes
                msg_inicio = json.dumps({'type': 'start'}).encode()
                for c in clientes.values():
                    try:
                        c.sendall(msg_inicio)
                    except:
                        pass
                break
    # Inicia loop principal do jogo
    loop_jogo()


def loop_jogo():
    while not estado_jogo['fim_jogo']:
        time.sleep(TICK)
        with trava:
            agora = time.time()
            # Move balas do atirador
            for b in estado_jogo['atirador']['balas']:
                b['y'] -= VEL_BALA
            # Remove fora da tela
            estado_jogo['atirador']['balas'] = [b for b in estado_jogo['atirador']['balas'] if b['y'] > 0]

            # Move balas inimigas
            for bi in estado_jogo['balas_inimigas']:
                bi['y'] += VEL_BALA_INIMIGA
            estado_jogo['balas_inimigas'] = [bi for bi in estado_jogo['balas_inimigas'] if bi['y'] < ALTURA]

            # —— Colisões: balas do atirador vs. inimigos ——
            remover_inimigos = set()
            remover_balas = set()
            for bi, b in enumerate(estado_jogo['atirador']['balas']):
                for ei, e in enumerate(estado_jogo['inimigos']):
                    if abs(e['x'] - b['x']) < LARGURA_INIMIGO and abs(e['y'] - b['y']) < ALTURA_INIMIGO:
                        remover_inimigos.add(ei)
                        remover_balas.add(bi)
                        break
            # remove de fato
            estado_jogo['inimigos'] = [e for i,e in enumerate(estado_jogo['inimigos']) if i not in remover_inimigos]
            estado_jogo['atirador']['balas'] = [b for i,b in enumerate(estado_jogo['atirador']['balas']) if i not in remover_balas]

            # Balas inimigas vs atirador
            if agora > estado_jogo['atirador']['imune_ate']:
                for bi in estado_jogo['balas_inimigas']:
                    if abs(bi['x'] - (estado_jogo['atirador']['x'] + 20)) < 20 and abs(bi['y'] - estado_jogo['atirador']['y']) < 20:
                        estado_jogo['atirador']['vidas'] -= 1
                        estado_jogo['atirador']['imune_ate'] = agora + DURACAO_IMUNIDADE
                        break

            # Aumenta velocidade dos inimigos com o tempo
            estado_jogo['velocidade_inimigo'] += 0.0005

            # Move inimigos para baixo
            for e in estado_jogo['inimigos']:
                e['y'] += estado_jogo['velocidade_inimigo']

            # Verifica condições de vitória/derrota
            if len(estado_jogo['inimigos']) == 0:
                estado_jogo['fim_jogo'] = True
                estado_jogo['vencedor'] = 'atirador'
            if any(e['y'] >= LIMITE_VERTICAL for e in estado_jogo['inimigos']):
                estado_jogo['fim_jogo'] = True
                estado_jogo['vencedor'] = 'inimigos'
            if estado_jogo['atirador']['vidas'] <= 0:
                estado_jogo['fim_jogo'] = True
                estado_jogo['vencedor'] = 'inimigos'

            # Envia estado para clientes
            estado = {'type': 'state', **estado_jogo}
            dados = json.dumps(estado).encode()
            for c in clientes.values():
                try:
                    c.sendall(dados)
                except:
                    pass


def main():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind((HOST, PORTA))
        s.listen(2)
        print("Aguardando jogadores...")

        for _ in (0,1):
            conn, _ = s.accept()
            init = conn.recv(1024)
            msg = json.loads(init.decode())
            papel = msg.get('role')
            if papel in ('atirador','inimigo'):
                clientes[papel] = conn
                conn.sendall(json.dumps({'type':'assign','role':papel}).encode())
                print(f"{papel.capitalize()} conectado")

        executor = ThreadPoolExecutor(max_workers=3)
        executor.submit(lidar_cliente, clientes['atirador'], 'atirador')
        executor.submit(lidar_cliente, clientes['inimigo'], 'inimigo')
        executor.submit(esperar_inicio)

if __name__ == '__main__':
    main()