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
        try:
            # SINTAXE ATUALIZADA (v2)
            realtime_conn = self.supabase.realtime
            channel = realtime_conn.channel('custom-insert-channel')
            channel.on(
                'postgres_changes',
                event='INSERT',
                schema='public',
                table='lancamentos',
                callback=self._callback
            )
            channel.subscribe()
            realtime_conn.connect() # Conecta ao websocket

            # Mantém a thread viva para continuar ouvindo
            while not self._stop_event.is_set():
                time.sleep(1)

        except Exception as e:
            print(f">>> ERRO na thread do ouvinte: {e}")
        finally:
            # Garante a desconexão ao parar
            if 'realtime_conn' in locals() and realtime_conn.is_connected():
                realtime_conn.disconnect()
            print(">>> OUVINTE SUPABASE REALTIME PARADO.")

    def stop(self):
        """Sinaliza para a thread parar."""
        self._stop_event.set()
