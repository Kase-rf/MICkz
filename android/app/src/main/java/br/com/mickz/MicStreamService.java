package br.com.mickz;

import android.app.Notification;
import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.PendingIntent;
import android.app.Service;
import android.media.AudioFormat;
import android.media.AudioRecord;
import android.media.MediaRecorder;
import android.os.Build;
import android.os.IBinder;
import android.os.PowerManager;
import android.util.Log;
import android.net.wifi.WifiManager;

import java.io.OutputStream;
import java.io.InputStream;
import java.net.InetSocketAddress;
import java.net.ServerSocket;
import java.net.Socket;
import java.nio.charset.StandardCharsets;

public final class MicStreamService extends Service {
    public static final String EXTRA_PORT = "port";
    public static final String EXTRA_WIFI_MODE = "wifi_mode";
    private static final String TAG = "MICkz";
    private static final String CHANNEL_ID = "mickz_stream";
    private static final int NOTIFICATION_ID = 49152;
    private static final int RATE = 48_000;
    private static final int FRAME_BYTES = 1_920;
    private volatile boolean running;
    private Thread worker;
    private AudioRecord recorder;
    private volatile ServerSocket serverSocket;
    private volatile Socket socket;
    private PowerManager.WakeLock wakeLock;
    private WifiManager.WifiLock wifiLock;
    private volatile int activePort = 49152;
    private volatile boolean wifiMode = true;

    @Override
    public void onCreate() {
        super.onCreate();
        createNotificationChannel();
        startForeground(NOTIFICATION_ID, notification("Preparando microfone…"));
    }

    @Override
    public int onStartCommand(android.content.Intent intent, int flags, int startId) {
        if (intent == null) {
            android.content.SharedPreferences preferences = getSharedPreferences("mickz_settings", MODE_PRIVATE);
            if (!preferences.getBoolean("service_requested", false)) {
                stopSelf();
                return START_NOT_STICKY;
            }
            activePort = preferences.getInt("service_port", 49152);
            wifiMode = preferences.getBoolean("service_wifi_mode", true);
        } else {
            activePort = intent.getIntExtra(EXTRA_PORT, 49152);
            wifiMode = intent.getBooleanExtra(EXTRA_WIFI_MODE, true);
            getSharedPreferences("mickz_settings", MODE_PRIVATE).edit()
                    .putBoolean("service_requested", true)
                    .putInt("service_port", activePort)
                    .putBoolean("service_wifi_mode", wifiMode)
                    .putString("service_state", "starting")
                    .apply();
        }
        if (running) return START_STICKY;
        acquireBackgroundLocks();
        final int port = activePort;
        running = true;
        worker = new Thread(() -> listen(port), "mickz-audio");
        worker.start();
        return START_STICKY;
    }

    private void acquireBackgroundLocks() {
        PowerManager power = (PowerManager) getSystemService(POWER_SERVICE);
        if (power != null && (wakeLock == null || !wakeLock.isHeld())) {
            wakeLock = power.newWakeLock(PowerManager.PARTIAL_WAKE_LOCK, "MICkz::AudioCapture");
            wakeLock.setReferenceCounted(false);
            wakeLock.acquire();
        }
        if (wifiMode) {
            WifiManager wifi = (WifiManager) getApplicationContext().getSystemService(WIFI_SERVICE);
            if (wifi != null && (wifiLock == null || !wifiLock.isHeld())) {
                int mode = Build.VERSION.SDK_INT >= 29
                        ? WifiManager.WIFI_MODE_FULL_LOW_LATENCY
                        : WifiManager.WIFI_MODE_FULL;
                wifiLock = wifi.createWifiLock(mode, "MICkz::WifiStreaming");
                wifiLock.setReferenceCounted(false);
                wifiLock.acquire();
            }
        }
    }

    private void releaseBackgroundLocks() {
        if (wifiLock != null && wifiLock.isHeld()) wifiLock.release();
        if (wakeLock != null && wakeLock.isHeld()) wakeLock.release();
        wifiLock = null;
        wakeLock = null;
    }

    private void setServiceState(String state) {
        getSharedPreferences("mickz_settings", MODE_PRIVATE).edit().putString("service_state", state).apply();
    }

    private void listen(int port) {
        try (ServerSocket listener = new ServerSocket()) {
            listener.setReuseAddress(true);
            listener.bind(new InetSocketAddress(port), 128);
            serverSocket = listener;
            setServiceState("waiting");
            updateNotification("Aguardando conexão do MICkz Linux na porta " + port);
            while (running) {
                boolean audioConnection = false;
                try (Socket connection = listener.accept()) {
                    socket = connection;
                    connection.setTcpNoDelay(true);
                    connection.setSoTimeout(2_000);
                    String request = readLine(connection.getInputStream());
                    OutputStream output = connection.getOutputStream();
                    if ("MICKZ/1 DISCOVER".equals(request)) {
                        String device = (Build.MANUFACTURER + " " + Build.MODEL).replace('\n', ' ').replace('\r', ' ');
                        output.write(("MICKZ/1 ANDROID " + device + "\n").getBytes(StandardCharsets.UTF_8));
                        output.flush();
                        continue;
                    }
                    if (!"MICKZ/1 STREAM".equals(request)) {
                        throw new IllegalArgumentException("Comando MICkz inválido.");
                    }
                    output.write("MICKZ/1 OK\n".getBytes(StandardCharsets.UTF_8));
                    output.flush();
                    connection.setSoTimeout(0);
                    audioConnection = true;
                    setServiceState("connected");
                    updateNotification("MICkz Linux conectado; transmitindo áudio");
                    streamAudio(connection, output);
                } catch (Exception error) {
                    if (running && !(error instanceof java.net.SocketTimeoutException)) {
                        Log.e(TAG, "Conexão encerrada", error);
                    }
                } finally {
                    socket = null;
                    releaseRecorder();
                    if (running && audioConnection) {
                        setServiceState("waiting");
                        updateNotification("Aguardando conexão do MICkz Linux na porta " + port);
                    }
                }
            }
        } catch (Exception error) {
            if (running) {
                Log.e(TAG, "Não foi possível iniciar o servidor", error);
                setServiceState("error");
                updateNotification("Falha: " + error.getMessage());
            }
        } finally {
            serverSocket = null;
            if (running) {
                running = false;
                getSharedPreferences("mickz_settings", MODE_PRIVATE).edit()
                        .putBoolean("service_requested", false).apply();
                releaseBackgroundLocks();
                stopForeground(STOP_FOREGROUND_DETACH);
                stopSelf();
            }
        }
    }

    private static String readLine(InputStream input) throws Exception {
        byte[] bytes = new byte[128];
        int length = 0;
        while (length < bytes.length) {
            int value = input.read();
            if (value < 0) return null;
            if (value == '\n') return new String(bytes, 0, length, StandardCharsets.UTF_8);
            bytes[length++] = (byte) value;
        }
        return null;
    }

    private void streamAudio(Socket connection, OutputStream output) throws Exception {
        int minimum = AudioRecord.getMinBufferSize(RATE, AudioFormat.CHANNEL_IN_MONO, AudioFormat.ENCODING_PCM_16BIT);
        if (minimum <= 0) throw new IllegalStateException("Formato de áudio não suportado pelo aparelho.");
        int bufferSize = Math.max(minimum, FRAME_BYTES * 4);
        AudioRecord activeRecorder = new AudioRecord(MediaRecorder.AudioSource.VOICE_RECOGNITION, RATE,
                AudioFormat.CHANNEL_IN_MONO, AudioFormat.ENCODING_PCM_16BIT, bufferSize);
        recorder = activeRecorder;
        if (activeRecorder.getState() != AudioRecord.STATE_INITIALIZED) {
            throw new IllegalStateException("Não foi possível inicializar o microfone.");
        }
        activeRecorder.startRecording();
        byte[] frame = new byte[FRAME_BYTES];
        int offset = 0;
        while (running && !connection.isClosed()) {
            int count = activeRecorder.read(frame, offset, frame.length - offset, AudioRecord.READ_BLOCKING);
            if (count < 0) throw new IllegalStateException("Erro ao capturar áudio: " + count);
            offset += count;
            if (offset == frame.length) {
                output.write(frame);
                offset = 0;
            }
        }
    }

    private void stopWorker() {
        running = false;
        ServerSocket listener = serverSocket;
        if (listener != null) {
            try { listener.close(); } catch (Exception ignored) { }
        }
        Socket activeSocket = socket;
        if (activeSocket != null) {
            try { activeSocket.close(); } catch (Exception ignored) { }
        }
        releaseRecorder();
        if (worker != null) {
            worker.interrupt();
            worker = null;
        }
    }

    private synchronized void releaseRecorder() {
        AudioRecord active = recorder;
        recorder = null;
        if (active != null) {
            try { active.stop(); } catch (IllegalStateException ignored) { }
            active.release();
        }
    }

    private void createNotificationChannel() {
        if (Build.VERSION.SDK_INT >= 26) {
            NotificationChannel channel = new NotificationChannel(CHANNEL_ID, "MICkz", NotificationManager.IMPORTANCE_LOW);
            getSystemService(NotificationManager.class).createNotificationChannel(channel);
        }
    }

    private Notification notification(String status) {
        android.content.Intent open = new android.content.Intent(this, MainActivity.class);
        PendingIntent pending = PendingIntent.getActivity(this, 0, open,
                PendingIntent.FLAG_UPDATE_CURRENT | (Build.VERSION.SDK_INT >= 23 ? PendingIntent.FLAG_IMMUTABLE : 0));
        if (Build.VERSION.SDK_INT >= 26) {
            return new Notification.Builder(this, CHANNEL_ID).setContentTitle("MICkz").setContentText(status)
                    .setSmallIcon(android.R.drawable.ic_btn_speak_now).setContentIntent(pending).setOngoing(true).build();
        }
        return new Notification.Builder(this).setContentTitle("MICkz").setContentText(status)
                .setSmallIcon(android.R.drawable.ic_btn_speak_now).setContentIntent(pending).setOngoing(true).build();
    }

    private void updateNotification(String status) {
        NotificationManager manager = getSystemService(NotificationManager.class);
        manager.notify(NOTIFICATION_ID, notification(status));
    }

    @Override
    public void onDestroy() {
        stopWorker();
        releaseBackgroundLocks();
        getSharedPreferences("mickz_settings", MODE_PRIVATE).edit()
                .putBoolean("service_requested", false).putString("service_state", "stopped").apply();
        stopForeground(STOP_FOREGROUND_REMOVE);
        super.onDestroy();
    }

    @Override
    public IBinder onBind(android.content.Intent intent) { return null; }
}
