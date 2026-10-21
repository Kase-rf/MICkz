package br.com.mickz;

import android.app.Notification;
import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.PendingIntent;
import android.app.Service;
import android.content.Intent;
import android.media.AudioFormat;
import android.media.AudioRecord;
import android.media.MediaRecorder;
import android.os.Build;
import android.os.IBinder;
import android.util.Log;

import java.io.OutputStream;
import java.net.InetSocketAddress;
import java.net.Socket;

public final class MicStreamService extends Service {
    public static final String EXTRA_HOST = "host";
    public static final String EXTRA_PORT = "port";
    private static final String TAG = "MICkz";
    private static final String CHANNEL_ID = "mickz_stream";
    private static final int NOTIFICATION_ID = 49152;
    private static final int RATE = 48_000;
    private static final int FRAME_BYTES = 1_920;
    private volatile boolean running;
    private Thread worker;
    private AudioRecord recorder;
    private Socket socket;

    @Override
    public void onCreate() {
        super.onCreate();
        createNotificationChannel();
        startForeground(NOTIFICATION_ID, notification("Preparando microfone…"));
    }

    @Override
    public int onStartCommand(Intent intent, int flags, int startId) {
        if (intent == null) {
            stopSelf();
            return START_NOT_STICKY;
        }
        stopWorker();
        String host = intent.getStringExtra(EXTRA_HOST);
        int port = intent.getIntExtra(EXTRA_PORT, 49152);
        running = true;
        worker = new Thread(() -> stream(host, port), "mickz-audio");
        worker.start();
        return START_NOT_STICKY;
    }

    private void stream(String host, int port) {
        try (Socket connection = new Socket()) {
            socket = connection;
            connection.setTcpNoDelay(true);
            connection.connect(new InetSocketAddress(host, port), 5_000);
            updateNotification("Conectado a " + host + ":" + port);

            int minimum = AudioRecord.getMinBufferSize(RATE, AudioFormat.CHANNEL_IN_MONO, AudioFormat.ENCODING_PCM_16BIT);
            if (minimum <= 0) throw new IllegalStateException("Formato de áudio não suportado pelo aparelho.");
            int bufferSize = Math.max(minimum, FRAME_BYTES * 4);
            recorder = new AudioRecord(MediaRecorder.AudioSource.VOICE_RECOGNITION, RATE,
                    AudioFormat.CHANNEL_IN_MONO, AudioFormat.ENCODING_PCM_16BIT, bufferSize);
            if (recorder.getState() != AudioRecord.STATE_INITIALIZED) {
                throw new IllegalStateException("Não foi possível inicializar o microfone.");
            }
            recorder.startRecording();
            byte[] frame = new byte[FRAME_BYTES];
            OutputStream output = connection.getOutputStream();
            int offset = 0;
            while (running) {
                int count = recorder.read(frame, offset, frame.length - offset, AudioRecord.READ_BLOCKING);
                if (count < 0) throw new IllegalStateException("Erro ao capturar áudio: " + count);
                offset += count;
                if (offset == frame.length) {
                    output.write(frame);
                    offset = 0;
                }
            }
        } catch (Exception error) {
            if (running) {
                Log.e(TAG, "Falha na transmissão", error);
                updateNotification("Falha: " + error.getMessage());
            }
        } finally {
            releaseRecorder();
            socket = null;
            if (running) {
                running = false;
                stopForeground(STOP_FOREGROUND_DETACH);
                stopSelf();
            }
        }
    }

    private void stopWorker() {
        running = false;
        if (socket != null) {
            try { socket.close(); } catch (Exception ignored) { }
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
        Intent open = new Intent(this, MainActivity.class);
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
        stopForeground(STOP_FOREGROUND_REMOVE);
        super.onDestroy();
    }

    @Override
    public IBinder onBind(Intent intent) { return null; }
}
