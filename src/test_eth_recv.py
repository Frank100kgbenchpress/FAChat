from ethernet import recv_frame

src, data = recv_frame()
print(f"Trama recibida de {src}: {data}")
