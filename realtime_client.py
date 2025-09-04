# realtime_client.py
import threading
from supabase import create_client, Client
import time

class SupabaseListener:
    def __init__(self, url, key, session_state):
        self.supabase: Client = create_client(url, key)
        self.session_state = session_state
        self._stop_event = threading.Event()

    def _callback(self, payload):
        """Esta função é chamada quando uma nova notificação chega."""
        print(">>> NOVO LANÇAMENTO RECEBIDO:", payload)
        self.session_state['new_launch_received'] = True

    def listen(self):
        """Inicia a escuta em uma thread."""
        print(">>> INICIANDO OUVINTE SUPABASE REALTIME...")
        realtime_conn = None  # Inicializa a variável como None
        try:
            realtime_conn = self.supabase.realtime
            
            # VERIFICAÇÃO DE SEGURANÇA: Checa se o cliente realtime foi criado
            if realtime_conn is None:
                raise Exception("O cliente Realtime não foi inicializado. Verifique a instalação da dependência 'realtime-py'.")

            channel = realtime_conn.channel('custom-insert-channel')
            channel.on(
                'postgres_changes',
                event='INSERT',
                schema='public',
                table='lancamentos',
                callback=self._callback
            )
            channel.subscribe()
            realtime_conn.connect()

            while not self._stop_event.is_set():
                time.sleep(1)

        except Exception as e:
            print(f">>> ERRO na thread do ouvinte: {e}")
        finally:
            # VERIFICAÇÃO DE SEGURANÇA: Só tenta desconectar se a conexão existia e estava ativa
            if realtime_conn and hasattr(realtime_conn, 'is_connected') and realtime_conn.is_connected():
                realtime_conn.disconnect()
            print(">>> OUVINTE SUPABASE REALTIME PARADO.")

    def stop(self):
        """Sinaliza para a thread parar."""
        self._stop_event.set()
