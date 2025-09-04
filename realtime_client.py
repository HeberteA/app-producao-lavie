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
        # Levanta a "bandeira" no session_state para o app principal ver
        self.session_state['new_launch_received'] = True

    def listen(self):
        """Inicia a escuta em uma thread."""
        print(">>> INICIANDO OUVINTE SUPABASE REALTIME...")
        channel = self.supabase.channel('custom-insert-channel')
        channel.on(
            'postgres_changes',
            event='INSERT',
            schema='public',
            table='lancamentos',
            callback=self._callback
        )
        subscription = channel.subscribe()

        # Mantém a thread viva para continuar ouvindo
        while not self._stop_event.is_set():
            time.sleep(1)
        
        # Se a thread for parada, cancela a inscrição
        print(">>> PARANDO OUVINTE SUPABASE REALTIME...")
        self.supabase.unsubscribe(subscription)

    def stop(self):
        """Sinaliza para a thread parar."""
        self._stop_event.set()