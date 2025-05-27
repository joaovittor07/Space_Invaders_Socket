import socket
import pygame
import json
import time
import threading

HOST = '0.0.0.0'
PORTA = 5555
FPS = 30
LARGURA, ALTURA = 640, 600

papel_cliente = None
jogo_iniciado = False
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
    'velocidade_inimigo': 0.1,
    'balas_inimigas': [],
    'fim_jogo': False,
    'vencedor': None
}

# Carregar sprites
img_atirador = pygame.image.load("assets/shooter.png")
img_inimigo = pygame.image.load("assets/enemy.png")
img_bala = pygame.image.load("assets/bullet.png")


def receber_estado(sock):
    global estado_jogo, papel_cliente, jogo_iniciado
    while True:
        try:
            dados = sock.recv(8192)
            if not dados:
                break
            msg = json.loads(dados.decode())
            if msg['type'] == 'assign':
                papel_cliente = msg['role']
            elif msg['type'] == 'start':
                jogo_iniciado = True
            elif msg['type'] == 'state':
                estado_jogo = msg
        except:
            break


def enviar_entrada(sock, acao):
    if papel_cliente:
        msg = json.dumps({'type': 'input', 'player': papel_cliente, 'action': acao}).encode()
        try:
            sock.sendall(msg)
        except:
            pass


def desenhar():
    tela.fill((0, 0, 0))
    if not jogo_iniciado:
        fonte = pygame.font.SysFont(None, 48)
        txt = "Pressione P quando estiver Preparado"
        texto = fonte.render(txt, True, (255, 255, 255))
        tela.blit(texto, (LARGURA//2 - texto.get_width()//2, ALTURA//2))
    else:
        # Desenhar inimigos
        for e in estado_jogo.get('inimigos', []):
            tela.blit(img_inimigo, (e['x'], e['y']))
        # Desenhar atirador
        sx, sy = estado_jogo['atirador']['x'], estado_jogo['atirador']['y']
        tela.blit(img_atirador, (sx, sy))
        # Desenhar balas
        for b in estado_jogo['atirador']['balas']:
            tela.blit(img_bala, (b['x'], b['y']))
        for bi in estado_jogo.get('balas_inimigas', []):
            tela.blit(img_bala, (bi['x'], bi['y']))
        # Fim de jogo
        if estado_jogo.get('fim_jogo'):
            fonte = pygame.font.SysFont(None, 72)
            msg = f"Vencedor: {estado_jogo['vencedor']}"
            texto = fonte.render(msg, True, (255, 0, 0))
            tela.blit(texto, (LARGURA//2 - texto.get_width()//2, ALTURA//2))
    pygame.display.flip()


def main():
    global tela
    pygame.init()
    tela = pygame.display.set_mode((LARGURA, ALTURA))
    pygame.display.set_caption("Cliente Inimigo")
    relogio = pygame.time.Clock()

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.connect((HOST, PORTA))
    sock.sendall(json.dumps({'type':'join','role':'inimigo'}).encode())
    threading.Thread(target=receber_estado, args=(sock,), daemon=True).start()

    tempo_fim = None
    rodando = True
    while rodando:
        for evento in pygame.event.get():
            if evento.type == pygame.QUIT:
                rodando = False
            if evento.type == pygame.KEYDOWN:
                if not jogo_iniciado and evento.key == pygame.K_p:
                    enviar_entrada(sock, 'pronto')
                elif jogo_iniciado and not estado_jogo.get('fim_jogo'):
                    if evento.key == pygame.K_LEFT:
                        enviar_entrada(sock, 'esquerda')
                    elif evento.key == pygame.K_RIGHT:
                        enviar_entrada(sock, 'direita')
                    elif evento.key == pygame.K_SPACE:
                        enviar_entrada(sock, 'atirar')
        desenhar()
        
        if estado_jogo.get('fim_jogo'):
            if tempo_fim is None:
                tempo_fim = time.time()
            elif time.time() - tempo_fim >= 5:
                rodando = False
                
        relogio.tick(FPS)

    pygame.quit()
    sock.close()

if __name__ == '__main__':
    main()