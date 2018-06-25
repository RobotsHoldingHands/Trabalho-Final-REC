#!/usr/bin/python
# -*- coding: utf-8 -*-

from socket import socket, AF_INET, SOCK_DGRAM
from Pacote import Pacote
from collections import Counter
import numpy as np
import json
import time

class TCP_em_UDP():
	def __init__(self, MTU=1500):
		self.sock = socket(AF_INET, SOCK_DGRAM)
		self.MTU = MTU
		self.MSS = MTU - 169
		self.ss = 1
		self.exponecial = True
		self.seq = np.random.randint(100)
		self.buffer = []
		self.indiceBuffer = 0
		self.listaACKs = []

	def abrir_conexao(self, ip, porta):
		tupla_conn = (ip, porta)
		pacote = Pacote()
		pacote.set([
				['porta_dest', porta],
				['syn', 1],
				['seq', self.seq]
			])
		raw_pacote = json.dumps(pacote.conteudo)
		print "Tentando se conectar a %s:%d." % (ip, porta)
		self.sock.sendto(raw_pacote, tupla_conn)
		raw_pacote, conn = self.sock.recvfrom(self.MTU)
		print "Pacote de resposta recebido."
		pacote.conteudo = json.loads(raw_pacote)
		if pacote.conteudo['flags']['syn'] and pacote.conteudo['flags']['ack']:
			print "O servidor enviou SYN ACK. Enviando ACK."
			self.ack = pacote.conteudo['seq'] + 1
			pacote.set([
					['porta_orig', pacote.conteudo['porta_dest']],
					['porta_dest', porta],
					['syn', 0],
					['seq', self.seq],
					['ack_n', self.ack]
				])
			raw_pacote = json.dumps(pacote.conteudo)
			self.sock.sendto(raw_pacote, tupla_conn)
			print "Conexão Estabelecida."
			
			return self.sock, tupla_conn
		else:
			print "O servidor não quis estabelecer conexão."
			print "Tentar novamente? [S/n]"
			if raw_input().lower() == "n":
				print "Adeus."
				return False
			else:
				print "Tentando novamente..."
				self.abrir_conexao(ip, porta)




	def enviar_dados(self, dados, sock, ip, porta):
		self.sock = sock
		tupla_conn = (ip, porta)
		pacote = Pacote()
		
		if (len(dados) > self.MSS):
			print "O pacote é muito grando e será segmentado."
			self.cria_segmentos(dados, porta)
		else:
			self.multiplexacao(dados, porta)

		if not self.buffer:
			print "O buffer está vazio."
		else:
			while self.indiceBuffer < len(self.buffer):
				for _ in range(self.ss):
					raw_pacote = json.dumps(self.buffer[self.indiceBuffer])
					self.sock.sendto(raw_pacote, tupla_conn)
					print "Segmento enviado."
					self.indiceBuffer += 1

				for _ in range(self.ss):
					if self.indiceBuffer >= len(self.buffer):
						break
					raw_pacote, conn = self.sock.recvfrom(self.MTU)
					pacote.conteudo = json.loads(raw_pacote)
					print "Pacote recebido. Tamanho:", len(raw_pacote)

					if self.ack - 1 == pacote.conteudo['seq']:
						if pacote.conteudo['flags']['ack']:
							if self.seq == pacote.conteudo['ack_n']:
								self.ack += len(pacote.conteudo['dados'])
								print "ACK recebido com sucesso."
							else:
								self.listaACKs.append(pacote.conteudo['ack_n'])
								if self.checaACKs():
									self.ss /= 2
									for i in range(len(self.buffer)):
										if self.buffer[i]['ack_n'] == pacote.conteudo['ack_n'] - 1:
											self.indiceBuffer = i
									print "3 ACKs duplicados. Fast Recovery."
						else:
							self.ack += len(pacote.conteudo['dados'])
							print "ACK recebido é um segmento."
					else:
						print json.dumps(pacote.conteudo, indent=4)
						pacote.set([
								['ack', 1],
								['ack_n', self.ack],
								['seq', self.seq],
								['dados', '']				
							])
						self.buffer.append(pacote.conteudo)
						print "Esse pacote não era esperado, enviando ACK."
						time.sleep(2.0)

	def checaACKs(self):
		acks_duplicados = Counter(self.listaACKs)
		for key, value in acks_duplicados.items():
			if value >= 3:
				return True

		return False


	def cria_segmentos(self, dados, porta):
		while len(dados) > self.MSS:
			self.multiplexacao(dados[0:self.MSS], porta, segmento=True)
			dados = dados[self.MSS:]
	
		if len(dados):
			self.multiplexacao(dados, porta)
	
	
	def multiplexacao(self, dados, porta, segmento=False):
		pacote = Pacote()
		if segmento:
			pacote.set([
					['ack', 0],
					['seq', self.seq],
					['ack_n', -1],
					['dados', dados],
					['porta_dest', porta]
				])
			self.seq += len(dados)
			self.buffer.append(pacote.conteudo)

		else:
			pacote.set([
					['seq', self.seq],
					['dados', dados],
					['porta_dest', porta],
					['ack', 1],
					['ack_n', self.ack]
				])
			self.seq += len(dados)
			self.buffer.append(pacote.conteudo)


	def fechar_conexao(self, sock, ip, porta):
		self.sock = sock
		tupla_conn = (ip, porta)
		print "Enviando pacote para fim da conexão."
		pacote = Pacote()
		pacote.set([['fin', 1]])
		raw_pacote = json.dumps(pacote.conteudo)
		self.sock.sendto(raw_pacote, tupla_conn)
		raw_pacote, conn = self.sock.recvfrom(self.MTU)
		if pacote.conteudo['flags']['fin'] == 1:
			self.sock.close()
			print "Conexão finalizada."
		else:
			print "O servidor não respondeu ao requerimento FIN"
			print "Deseja forçar a interrupção [s/N]?"
			if(raw_input().lower() == 's'):
				self.sock.close()
				print "Conexão terminada a força."
			else:
				print "Tentando finalizar a conexão novamente..."
				self.fechar_conexao(sock, ip, porta)

	
	def iniciar_servidor(self, ip, porta):
		tupla_conn = (ip, porta)
		self.sock.bind(tupla_conn)
		pacote = Pacote()
		montador = []
		print "Olá! Servidar iniciando na porta", porta
		
		while True:
			raw_pacote, conn = self.sock.recvfrom(self.MTU)
			pacote.conteudo = json.loads(raw_pacote)
			pacote.set([
					['porta_orig', pacote.conteudo['porta_dest']],
					['port_dest', conn[1]]			
				])

			if pacote.conteudo['flags']['syn']:
				print conn[0], "deseja se conectar."
				self.ack = pacote.conteudo['seq'] + 1
				pacote.set([
						['ack', 1],
						['rwnd', 32768],
						['seq', self.seq],
						['ack_n', self.ack]			
					])

				raw_pacote = json.dumps(pacote.conteudo)
				self.sock.sendto(raw_pacote, conn)
				print "Pacote SYN ACK enviado."
				raw_pacote, conn = self.sock.recvfrom(self.MTU)
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
				break
			else:
				print "Pacote recebido de tamanho", len(pacote.conteudo['dados'])
				if self.ack - 1 == pacote.conteudo['seq']:
					if pacote.conteudo['flags']['ack']:
						if self.seq == pacote.conteudo['ack_n'] - 1:
							self.ack += len(pacote.conteudo['dados'])
							self.buffer.append(pacote.conteudo)
							montador.append(pacote.conteudo['dados'])
							pacote.set([
									['ack_n', self.ack],
									['seq', self.seq],
									['dados', '']
								])
							self.seq += len(pacote.conteudo['dados'])
							print "Pacote recebido..."
							print "".join(montador)
							montador = []
						else:
							self.listaACKs.append(pacote.conteudo['ack_n'])
							if self.checaACKs() == True:
								self.ss /= 2
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
						print "O pacote é um segmento, esperando mais dados"

				else:
					pacote.set([
							['ack_n', self.ack],
							['seq', self.seq],
							['dados', '']		
						])
					self.buffer.append(pacote.conteudo)
					print self.ack-1, pacote.conteudo['seq']


			if not self.buffer:
				print "O buffer está vazio."
			else:
				while self.indiceBuffer < len(self.buffer):
					for _ in range(self.ss):
						if self.indiceBuffer >= len(self.buffer):
							break
						raw_pacote = json.dumps(self.buffer[self.indiceBuffer])
						self.sock.sendto(raw_pacote, conn)
						print "Segmento enviado."
						self.indiceBuffer += 1

if __name__ == "__main__":
	tcp = TCP_em_UDP()
	tcp.iniciar_servidor('127.0.0.1', 3883)





