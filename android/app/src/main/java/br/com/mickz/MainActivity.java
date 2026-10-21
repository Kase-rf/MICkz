package br.com.mickz;

import android.Manifest;
import android.app.Activity;
import android.content.Intent;
import android.content.pm.PackageManager;
import android.os.Build;
import android.os.Bundle;
import android.view.Gravity;
import android.widget.Button;
import android.widget.EditText;
import android.widget.LinearLayout;
import android.widget.TextView;
import android.widget.Toast;

public final class MainActivity extends Activity {
    private static final int PERMISSION_REQUEST = 1;
    private EditText hostField;
    private EditText portField;

    @Override
    protected void onCreate(Bundle state) {
        super.onCreate(state);
        LinearLayout layout = new LinearLayout(this);
        layout.setOrientation(LinearLayout.VERTICAL);
        layout.setPadding(28, 32, 28, 24);

        TextView title = new TextView(this);
        title.setText("MICkz — microfone Android para Linux");
        title.setTextSize(21);
        layout.addView(title);

        TextView help = new TextView(this);
        help.setText("Informe o IP do computador na rede. Para USB, use 127.0.0.1 após executar adb reverse no Linux.");
        help.setPadding(0, 16, 0, 12);
        layout.addView(help);

        hostField = new EditText(this);
        hostField.setSingleLine(true);
        hostField.setHint("IP do Linux (ex.: 192.168.1.20)");
        hostField.setText("127.0.0.1");
        layout.addView(hostField);

        portField = new EditText(this);
        portField.setSingleLine(true);
        portField.setInputType(2);
        portField.setHint("Porta");
        portField.setText("49152");
        layout.addView(portField);

        Button connect = new Button(this);
        connect.setText("Conectar");
        connect.setOnClickListener(view -> requestMicAndStart());
        layout.addView(connect);

        Button disconnect = new Button(this);
        disconnect.setText("Desconectar");
        disconnect.setOnClickListener(view -> stopService(new Intent(this, MicStreamService.class)));
        layout.addView(disconnect);

        TextView footer = new TextView(this);
        footer.setGravity(Gravity.CENTER);
        footer.setText("O áudio usa PCM mono 48 kHz. Mantenha a notificação MICkz ativa durante as chamadas.");
        footer.setPadding(0, 20, 0, 0);
        layout.addView(footer);
        setContentView(layout);
    }

    private void requestMicAndStart() {
        if (checkSelfPermission(Manifest.permission.RECORD_AUDIO) != PackageManager.PERMISSION_GRANTED) {
            requestPermissions(new String[]{Manifest.permission.RECORD_AUDIO}, PERMISSION_REQUEST);
            return;
        }
        startStream();
    }

    private void startStream() {
        String host = hostField.getText().toString().trim();
        int port;
        try {
            port = Integer.parseInt(portField.getText().toString().trim());
            if (host.isEmpty() || port < 1 || port > 65535) throw new NumberFormatException();
        } catch (NumberFormatException error) {
            Toast.makeText(this, "Informe um host e uma porta válidos.", Toast.LENGTH_SHORT).show();
            return;
        }
        Intent intent = new Intent(this, MicStreamService.class);
        intent.putExtra(MicStreamService.EXTRA_HOST, host);
        intent.putExtra(MicStreamService.EXTRA_PORT, port);
        if (Build.VERSION.SDK_INT >= 26) startForegroundService(intent);
        else startService(intent);
    }

    @Override
    public void onRequestPermissionsResult(int requestCode, String[] permissions, int[] results) {
        super.onRequestPermissionsResult(requestCode, permissions, results);
        if (requestCode == PERMISSION_REQUEST && results.length > 0 && results[0] == PackageManager.PERMISSION_GRANTED) {
            startStream();
        } else if (requestCode == PERMISSION_REQUEST) {
            Toast.makeText(this, "A permissão de microfone é necessária para transmitir áudio.", Toast.LENGTH_LONG).show();
        }
    }
}
