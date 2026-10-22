package br.com.mickz;

import android.Manifest;
import android.app.Activity;
import android.content.Intent;
import android.content.SharedPreferences;
import android.content.pm.PackageManager;
import android.os.Build;
import android.os.Bundle;
import android.view.Gravity;
import android.view.View;
import android.widget.Button;
import android.widget.EditText;
import android.widget.LinearLayout;
import android.widget.RadioButton;
import android.widget.RadioGroup;
import android.widget.TextView;
import android.widget.Toast;

public final class MainActivity extends Activity {
    private static final int PERMISSION_REQUEST = 1;
    private static final String PREFS = "mickz_settings";
    private static final String PREF_WIFI_HOST = "wifi_host";
    private EditText hostField;
    private EditText portField;
    private RadioButton wifiMode;
    private RadioButton usbMode;
    private TextView help;
    private SharedPreferences preferences;

    @Override
    protected void onCreate(Bundle state) {
        super.onCreate(state);
        LinearLayout layout = new LinearLayout(this);
        layout.setOrientation(LinearLayout.VERTICAL);
        layout.setPadding(28, 32, 28, 24);
        preferences = getSharedPreferences(PREFS, MODE_PRIVATE);

        TextView title = new TextView(this);
        title.setText("MICkz — microfone Android para Linux");
        title.setTextSize(21);
        layout.addView(title);

        help = new TextView(this);
        help.setText("Wi-Fi: conecte o celular e o PC à mesma rede e informe o IP do PC. Não use 127.0.0.1.");
        help.setPadding(0, 16, 0, 12);
        layout.addView(help);

        TextView modeLabel = new TextView(this);
        modeLabel.setText("Modo de conexão");
        layout.addView(modeLabel);

        RadioGroup modes = new RadioGroup(this);
        modes.setOrientation(RadioGroup.HORIZONTAL);
        wifiMode = new RadioButton(this);
        wifiMode.setId(View.generateViewId());
        wifiMode.setText("Wi-Fi (sem cabo)");
        usbMode = new RadioButton(this);
        usbMode.setId(View.generateViewId());
        usbMode.setText("USB");
        modes.addView(wifiMode);
        modes.addView(usbMode);
        layout.addView(modes);

        hostField = new EditText(this);
        hostField.setSingleLine(true);
        hostField.setHint("IP do PC (ex.: 192.168.1.20)");
        hostField.setText(preferences.getString(PREF_WIFI_HOST, ""));
        layout.addView(hostField);

        portField = new EditText(this);
        portField.setSingleLine(true);
        portField.setInputType(2);
        portField.setHint("Porta");
        portField.setText("49152");
        layout.addView(portField);

        modes.setOnCheckedChangeListener((group, checkedId) -> {
            if (checkedId == usbMode.getId()) {
                hostField.setText("127.0.0.1");
                hostField.setEnabled(false);
                help.setText("USB: conecte e autorize o celular; no Linux, use Configurar USB. O host será 127.0.0.1.");
            } else {
                hostField.setEnabled(true);
                hostField.setText(preferences.getString(PREF_WIFI_HOST, ""));
                help.setText("Wi-Fi: conecte o celular e o PC à mesma rede e informe o IP do PC. Não use 127.0.0.1.");
            }
        });
        wifiMode.setChecked(true);

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
        if (wifiMode.isChecked() && "127.0.0.1".equals(host)) {
            Toast.makeText(this, "No Wi-Fi, informe o IP do PC mostrado no MICkz Linux.", Toast.LENGTH_LONG).show();
            return;
        }
        if (wifiMode.isChecked()) {
            preferences.edit().putString(PREF_WIFI_HOST, host).apply();
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
