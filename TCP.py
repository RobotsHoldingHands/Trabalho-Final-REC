#!/usr/bin/python
# -*- coding: utf-8 -*-

from socket import socket, AF_INET, SOCK_DGRAM
from Pacote import Pacote
from collections import Counter
import numpy as np
import json
import time

class TCP_em_UDP():
	# Construtor da classe com MTU opcional, o padrão é 1500
	def __init__(self, MTU=1500):
		self.sock = socket(AF_INET, SOCK_DGRAM)
		self.MTU = MTU
		# Criando pacote padrão para definir dinamicamente o MSS
		pacote = Pacote()
		pacote.set([
			['porta_orig', 65536],
			['porta_dest', 65536],
			['seq', 999999],
			['ack_n', 999999],
			['RTT', time.time()],
			['ack', 1],
			['syn', 1],
			['fin', 1]			
		])
		self.MSS = MTU - len(json.dumps(pacote.conteudo))
		self.cwnd = 1
		# Variavel que determina se o crescimento da cwnd será exponencial ou linear
		self.exponencial = True
		self.seq = np.random.randint(100)
		# Buffer de envio
		self.buffer = []
		self.indiceBuffer = 0
		self.listaACKs = []
		self.timeout = 0
		self.ssthresh = 64 * 1024

	# Função que inicia a conexão de um client
	def abrir_conexao(self, ip, porta):
		tupla_conn = (ip, porta)
		pacote = Pacote()
		pacote.set([
				['porta_dest', porta],
				['syn', 1],
				['seq', self.seq],
				['RTT', time.time()]
			])
		raw_pacote = json.dumps(pacote.conteudo)
		print "Tentando se conectar a %s:%d." % (ip, porta)
		# Enviando requisição SYN
		self.sock.sendto(raw_pacote, tupla_conn)
		self.sock.settimeout(5.0)
		# Caso o pacote se perca o client tenta reenviar a requisição
		while True:
			try:
				raw_pacote, conn = self.sock.recvfrom(self.MTU)
				break
			except:
				self.sock.sendto(raw_pacote, tupla_conn)
				print "Não houve resposta do servidor, tentando novamente."
				
		print "Pacote de resposta recebido."
		pacote.conteudo = json.loads(raw_pacote)
		if pacote.conteudo['flags']['syn'] and pacote.conteudo['flags']['ack']:
			print "O servidor enviou SYN ACK. Enviando ACK."
			self.timeout = min(8, pacote.conteudo['RTT'])
			self.sock.settimeout(self.timeout)
			# Caso haja resposta o RTT é calculado e além disso uma resposta é gerada e enviada
			self.ack = pacote.conteudo['seq'] + 1
			pacote.set([
					['porta_orig', pacote.conteudo['porta_dest']],
					['porta_dest', porta],
					['syn', 0],
					['seq', self.seq],
					['ack_n', self.ack],
					['RTT', time.time()]
				])
			raw_pacote = json.dumps(pacote.conteudo)
			self.sock.sendto(raw_pacote, tupla_conn)
			print "Conexão Estabelecida."
			
			# O socket e as informações de conexão são retornadas para o client
			return self.sock, tupla_conn
		else:
			# Caso o servidor rejeite a conexão há uma opção de tentar novamente ou abandonar a conexão
			print "O servidor não quis estabelecer conexão."
			print "Tentar novamente? [S/n]"
			if raw_input().lower() == "n":
				print "Adeus."
				return False
			else:
				print "Tentando novamente..."
				self.abrir_conexao(ip, porta)



	# Função que envia dados de um client para o servidor
	def enviar_dados(self, dados, sock, ip, porta):
		self.sock = sock
		tupla_conn = (ip, porta)
		pacote = Pacote()
		
		# Caso os dados sejam maiores que o MSS o pacote será segmentado
		if (len(dados) >= self.MSS):
			print "O pacote é muito grande e será (provavelmente) dividido em", len(dados)//self.MSS + 1, "segmentos."
			self.cria_segmentos(dados, porta)
		else:
			self.multiplexacao(dados, porta)

		if not self.buffer:
			print "O buffer está vazio."
		else:
			# Loop de envio e recebimento dos dados
			while self.indiceBuffer < len(self.buffer):
				cont = 0
				if self.cwnd * self.MSS > self.ssthresh:
					self.exponencial = False

				pacotes_enviados = 0
				# Loop de envio do que está no buffer de acordo com o cwnd
				while cont < self.cwnd:
					if self.indiceBuffer >= len(self.buffer):
						pacotes_enviados = cont
						break
					raw_pacote = json.dumps(self.buffer[self.indiceBuffer])
					self.sock.sendto(raw_pacote, tupla_conn)
					self.indiceBuffer += 1
					cont += 1
					pacotes_enviados += 1

				print cont, "segmentos enviados."

				cont = 0
				# Loop de recebimento dos dados
				while cont < pacotes_enviados:
					while True:
						try:
							raw_pacote, conn = self.sock.recvfrom(self.MTU)
							break
						except:
							print "Timeout, iniciando a partida lenta"
							self.ssthresh = self.cwnd * self.MSS/2
							self.exponencial = True
							self.cwnd = 1
							self.sock.sendto(raw_pacote, tupla_conn)
						

					pacote.conteudo = json.loads(raw_pacote)

					if self.ack - 1 == pacote.conteudo['seq']:
						if self.seq == pacote.conteudo['ack_n'] - 1:
							self.ack += len(pacote.conteudo['dados'])
							self.timeout = min(8, pacote.conteudo['RTT'])
							self.sock.settimeout(self.timeout)
							print "Novo valor de timeout:", self.timeout
							print "ACK do pacote final recebido."
							if self.exponencial:
								self.cwnd = self.cwnd * 2
							else:
								self.cwnd = self.cwnd + 1
						else:
							self.listaACKs.append(pacote.conteudo['ack_n'])
							if self.checaACKs():
								if self.cwnd > 1:
									self.cwnd /= 2
									self.ssthresh = self.cwnd * self.MSS/2
								self.exponencial = False
								for i in range(len(self.buffer)):
									if self.buffer[i]['seq'] == pacote.conteudo['ack_n'] - 1:
										self.indiceBuffer = i
										break
								print "3 ACKs duplicados. Fast Recovery."
								self.listaACKs = []
							else:
								if self.exponencial:
									self.cwnd = self.cwnd * 2
								else:
									self.cwnd = self.cwnd + 1
							
					else:
						pacote.set([
								['ack', 1],
								['ack_n', self.ack],
								['seq', self.seq],
								['dados', ''],
								['RTT', time.time()]			
							])
						self.buffer.append(pacote.conteudo)
						print "Esse pacote não era esperado, enviando ACK."
		
					cont += 1

	# Verifica se há 3 ACKs duplicados e retorna verdadeiro ou falso
	def checaACKs(self):
		acks_duplicados = Counter(self.listaACKs)
		for key, value in acks_duplicados.items():
			if value >= 3:
				return True

		return False


	# Quebra os dados em segmentos de acordo com o MSS
	def cria_segmentos(self, dados, porta):
		while len(dados) > self.MSS:
			self.multiplexacao(dados[0:self.MSS], porta, segmento=True)
			dados = dados[self.MSS:]
	
		if len(dados):
			self.multiplexacao(dados, porta)
	
	
	# Empacota dados brutos e os coloca no buffer
	def multiplexacao(self, dados, porta, segmento=False):
		pacote = Pacote()
		if segmento:
			pacote.set([
					['ack', 0],
					['seq', self.seq],
					['ack_n', -1],
					['dados', dados],
					['porta_dest', porta],
					['RTT', time.time()]
				])
			self.seq += len(dados)
			self.buffer.append(pacote.conteudo)

		else:
			pacote.set([
					['seq', self.seq],
					['dados', dados],
					['porta_dest', porta],
					['ack', 1],
					['ack_n', self.ack],
					['RTT', time.time()]
				])
			self.seq += len(dados)
			self.buffer.append(pacote.conteudo)


	# Envia requerimento FIN, funcionamento parecido com o do requerimento SYN
	def fechar_conexao(self, sock, ip, porta):
		self.sock = sock
		tupla_conn = (ip, porta)
		print "Enviando pacote para fim da conexão."
		pacote = Pacote()
		pacote.set([['fin', 1]])
		raw_pacote = json.dumps(pacote.conteudo)
		self.sock.sendto(raw_pacote, tupla_conn)
		while True:
			try:
				raw_pacote, conn = self.sock.recvfrom(self.MTU)
				break
			except:
				print "Tempo limite atingido, reenviando pacote FIN"
				self.sock.sendto(raw_pacote, tupla_conn)				

		if pacote.conteudo['flags']['fin'] == 1:
			self.sock.close()
			print "Conexão finalizada."
		else:
			print "O servidor não respondeu corretamente ao requerimento FIN."
			print "Deseja forçar a interrupção [s/N]?"
			if(raw_input().lower() == 's'):
				self.sock.close()
				print "Conexão terminada a força."
			else:
				print "Tentando finalizar a conexão novamente..."
				self.fechar_conexao(sock, ip, porta)

	
	# Simula um servidor de ACKs
	def iniciar_servidor(self, ip, porta):
		tupla_conn = (ip, porta)
		self.sock.bind(tupla_conn)
		self.sock.settimeout(5)
		pacote = Pacote()
		montador = []
		print "Olá! Servidor iniciando na porta", porta
		
		# Recebe dados até que uma conexão seja estabelecida e posteriormente finalizada
		while True:
			cont = 0
			# Loop que recebe os dados
			while cont < self.cwnd:
				if self.cwnd * self.MSS > self.ssthresh:
					self.exponencial = False
				while True:
					try:
						raw_pacote, conn = self.sock.recvfrom(self.MTU)
						break
					except:
						self.ssthresh = self.cwnd * self.MSS/2
						self.exponencial = True
						self.cwnd = 1

				pacote.conteudo = json.loads(raw_pacote)
				pacote.set([
						['porta_orig', pacote.conteudo['porta_dest']],
						['port_dest', conn[1]]			
					])
				if pacote.conteudo['flags']['syn']:
					print conn[0], "deseja se conectar."
					self.ack = pacote.conteudo['seq'] + 1
					self.timeout = min(8, round(4*(time.time() - pacote.conteudo['RTT']), 4))
					pacote.set([
							['ack', 1],
							['rwnd', 32768],
							['seq', self.seq],
							['ack_n', self.ack],
							['RTT', self.timeout]		
						])
					raw_pacote = json.dumps(pacote.conteudo)
					self.sock.settimeout(self.timeout)
					self.sock.sendto(raw_pacote, conn)
					print "Pacote SYN ACK enviado."
					while True:
						try:
							raw_pacote, conn = self.sock.recvfrom(self.MTU)
							break
						except:
							print "Timeout, iniciando a partida lenta"
							self.ssthresh = self.cwnd * self.MSS/2
							self.exponencial = True
							self.cwnd = 1
							self.sock.sendto(raw_pacote, tupla_conn)

					pacote.conteudo = json.loads(raw_pacote)
					if pacote.conteudo['flags']['ack'] and pacote.conteudo['ack_n'] - 1 == self.seq:
						print "Conexão estabelecida!"
					else:
						print "Erro ao estabelecer conexão!"
						break

				elif pacote.conteudo['flags']['fin']:
					raw_pacote = json.dumps(pacote.conteudo)
					self.sock.sendto(raw_pacote, conn)
					print "O cliente gostaria de encerrar a conexão."
					self.sock.close()
					print "Conexão encerrada."
					exit()
				else:
					if self.ack - 1 == pacote.conteudo['seq']:
						print "Pacote recebido de tamanho", len(pacote.conteudo['dados'])
						if pacote.conteudo['flags']['ack']:
							if self.seq == pacote.conteudo['ack_n'] - 1:
								self.ack += len(pacote.conteudo['dados'])
								#self.buffer.append(pacote.conteudo)
								montador.append(pacote.conteudo['dados'])
								self.timeout = min(8, round(4*(time.time() - pacote.conteudo['RTT']), 4))
								pacote.set([
										['ack', 1],
										['ack_n', self.ack],
										['seq', self.seq],
										['dados', ''],
										['RTT', self.timeout]
									])
								self.buffer.append(pacote.conteudo) #Adicionado
								self.seq += len(pacote.conteudo['dados'])
								print "Remontando pacote."
								print "Numero de bytes após remontagem do pacote:", len("".join(montador)) # Trocar
								print "Primeiros 100 caracteres: ", "".join(montador)[0:100]
								if self.exponencial:
									self.cwnd = self.cwnd * 2
								else:
									self.cwnd = self.cwnd + 1
								montador = []
								break
							else:
								self.listaACKs.append(pacote.conteudo['ack_n'])
								if self.checaACKs() == True:
									if self.cwnd > 1:
										self.cwnd /= 2
										self.ssthresh = self.cwnd * self.MSS/2
									for i in range(len(self.buffer)):
										if self.buffer[i]['ack_n'] == pacote.conteudo['ack_n'] - 1:
											self.indiceBuffer = i
									print "3 ACKs duplicados. Fast Recovery."
						else:
							self.ack += len(pacote.conteudo['dados'])
							montador.append(pacote.conteudo['dados'])
							pacote.set([
									['ack_n', self.ack],
									['seq', self.seq],
									['ack', 0],
									['dados', '']
								])
							self.buffer.append(pacote.conteudo)
							if self.exponencial:
								self.cwnd = self.cwnd * 2
							else:
								self.cwnd = self.cwnd + 1
							print "O pacote é um segmento, esperando mais dados..."

					else:
						pacote.set([
								['ack', 1],
								['ack_n', self.ack],
								['seq', self.seq],
								['dados', '']		
							])
						self.buffer.append(pacote.conteudo)
						'''raw_pacote = json.dumps(pacote.conteudo)
						self.sock.sendto(raw_pacote, conn)'''
						print "O pacote não era esperado, enviando ACK."
						self.listaACKs.append(self.ack)
						if self.checaACKs():
							if self.cwnd > 1:
								self.cwnd /= 2
								self.ssthresh = self.cwnd * self.MSS/2
							self.exponencial = False
							print "Foram enviados 3 ACKs duplicados, cortando janela."
							self.listaACKS = []


				cont += 1
			

			pacotes_recebidos = cont + 1
			cont = 0

			if not self.buffer:
				print "O buffer está vazio."
			else:
				# Loop que envia os dados de acordo com a cwnd
				while self.indiceBuffer < len(self.buffer):
					while cont < pacotes_recebidos:
						if self.indiceBuffer >= len(self.buffer):
							break
						raw_pacote = json.dumps(self.buffer[self.indiceBuffer])
						self.sock.sendto(raw_pacote, conn)
						self.indiceBuffer += 1
						cont += 1

					print "Enviados", cont, "ACK's"


# Caso o arquivo seja executado diretamente ele cria um servidor local na porta 3883
if __name__ == "__main__":
	tcp = TCP_em_UDP()
	tcp.iniciar_servidor('127.0.0.1', 3883)





