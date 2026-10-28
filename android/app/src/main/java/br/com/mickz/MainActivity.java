package br.com.mickz;

import android.Manifest;
import android.app.Activity;
import android.content.Intent;
import android.content.pm.PackageManager;
import android.graphics.Color;
import android.graphics.Typeface;
import android.graphics.drawable.GradientDrawable;
import android.os.Build;
import android.os.Bundle;
import android.view.Gravity;
import android.view.View;
import android.widget.Button;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.TextView;
import android.widget.Toast;

import java.net.Inet4Address;
import java.net.NetworkInterface;
import java.util.Enumeration;

public final class MainActivity extends Activity {
    private static final int PERMISSION_REQUEST = 1;
    private static final int PORT = 49152;
    private static final int BG = Color.rgb(8, 14, 21);
    private static final int PANEL = Color.rgb(14, 23, 33);
    private static final int PANEL_ALT = Color.rgb(18, 29, 41);
    private static final int TEXT = Color.rgb(232, 240, 248);
    private static final int MUTED = Color.rgb(145, 164, 184);
    private static final int ACCENT = Color.rgb(20, 218, 178);
    private static final int BORDER = Color.rgb(29, 43, 57);
    private static final String PREFS = "mickz_settings";

    private boolean wifiMode = true;
    private TextView address;
    private TextView statusTitle;
    private TextView statusDetail;
    private TextView statusDot;
    private Button wifiButton;
    private Button usbButton;
    private Button startButton;
    private Button stopButton;
    private boolean resumed;

    @Override
    protected void onCreate(Bundle state) {
        super.onCreate(state);
        getWindow().setStatusBarColor(BG);
        getWindow().setNavigationBarColor(BG);
        if (Build.VERSION.SDK_INT >= 23) {
            getWindow().getDecorView().setSystemUiVisibility(0);
        }
        wifiMode = getPreferences(MODE_PRIVATE).getBoolean("wifi_mode", true);
        buildInterface();
    }

    private void buildInterface() {
        ScrollView scroll = new ScrollView(this);
        scroll.setFillViewport(true);
        scroll.setBackgroundColor(BG);
        LinearLayout page = new LinearLayout(this);
        page.setOrientation(LinearLayout.VERTICAL);
        page.setPadding(dp(24), dp(24), dp(24), dp(24));
        scroll.addView(page);

        LinearLayout header = new LinearLayout(this);
        header.setGravity(Gravity.CENTER_VERTICAL);
        header.setPadding(0, dp(4), 0, dp(24));
        page.addView(header, matchWrap());

        TextView logo = new TextView(this);
        logo.setText("♫");
        logo.setTextColor(ACCENT);
        logo.setTextSize(29);
        logo.setGravity(Gravity.CENTER);
        logo.setBackground(rounded(PANEL_ALT, ACCENT, 2, 18));
        header.addView(logo, new LinearLayout.LayoutParams(dp(56), dp(56)));

        LinearLayout brand = new LinearLayout(this);
        brand.setOrientation(LinearLayout.VERTICAL);
        brand.setPadding(dp(14), 0, 0, 0);
        header.addView(brand, new LinearLayout.LayoutParams(0, -2, 1));
        TextView title = label("MICkz", 25, TEXT, true);
        brand.addView(title);
        TextView subtitle = label("Microfone do celular no seu PC", 14, MUTED, false);
        brand.addView(subtitle);

        TextView settings = label("⚙", 26, MUTED, false);
        settings.setGravity(Gravity.CENTER);
        header.addView(settings, new LinearLayout.LayoutParams(dp(44), dp(48)));

        TextView modeTitle = label("Tipo de conexão", 18, TEXT, true);
        page.addView(modeTitle);
        TextView modeDescription = label("Escolha como deseja se conectar ao seu PC.", 14, MUTED, false);
        LinearLayout.LayoutParams descParams = matchWrap();
        descParams.topMargin = dp(4);
        page.addView(modeDescription, descParams);

        LinearLayout modeCard = new LinearLayout(this);
        modeCard.setOrientation(LinearLayout.HORIZONTAL);
        modeCard.setPadding(dp(8), dp(8), dp(8), dp(8));
        modeCard.setBackground(rounded(PANEL, BORDER, 1, 20));
        LinearLayout.LayoutParams modeCardParams = matchWrap();
        modeCardParams.topMargin = dp(14);
        page.addView(modeCard, modeCardParams);
        wifiButton = modeButton("⌁   Wi-Fi", true);
        usbButton = modeButton("♆   USB", false);
        modeCard.addView(wifiButton, new LinearLayout.LayoutParams(0, dp(58), 1));
        LinearLayout.LayoutParams usbParams = new LinearLayout.LayoutParams(0, dp(58), 1);
        usbParams.leftMargin = dp(8);
        modeCard.addView(usbButton, usbParams);
        updateModeButtons();

        address = label("", 12, MUTED, false);
        LinearLayout.LayoutParams addressParams = matchWrap();
        addressParams.topMargin = dp(10);
        addressParams.leftMargin = dp(8);
        page.addView(address, addressParams);
        updateAddress();

        LinearLayout micArea = new LinearLayout(this);
        micArea.setOrientation(LinearLayout.VERTICAL);
        micArea.setGravity(Gravity.CENTER_HORIZONTAL);
        micArea.setPadding(0, dp(34), 0, dp(30));
        page.addView(micArea, matchWrap());
        startButton = new Button(this);
        startButton.setAllCaps(false);
        startButton.setText("🎙\nIniciar microfone");
        startButton.setTextSize(17);
        startButton.setTextColor(TEXT);
        startButton.setTypeface(Typeface.DEFAULT, Typeface.BOLD);
        startButton.setBackground(rounded(PANEL_ALT, ACCENT, 2, 100));
        startButton.setElevation(dp(8));
        micArea.addView(startButton, new LinearLayout.LayoutParams(dp(220), dp(220)));
        startButton.setOnClickListener(v -> requestMicAndStart());

        stopButton = new Button(this);
        stopButton.setAllCaps(false);
        stopButton.setText("◌   Parar microfone");
        stopButton.setTextSize(15);
        stopButton.setTextColor(MUTED);
        stopButton.setBackground(rounded(PANEL_ALT, BORDER, 1, 40));
        LinearLayout.LayoutParams stopParams = new LinearLayout.LayoutParams(dp(240), dp(58));
        stopParams.topMargin = dp(20);
        micArea.addView(stopButton, stopParams);
        stopButton.setOnClickListener(v -> stopMicrophone());

        LinearLayout statusCard = new LinearLayout(this);
        statusCard.setOrientation(LinearLayout.VERTICAL);
        statusCard.setPadding(dp(18), dp(16), dp(18), dp(16));
        statusCard.setBackground(rounded(PANEL, BORDER, 1, 20));
        page.addView(statusCard, matchWrap());
        LinearLayout statusLine = new LinearLayout(this);
        statusLine.setGravity(Gravity.CENTER_VERTICAL);
        statusCard.addView(statusLine, matchWrap());
        statusDot = label("●", 15, ACCENT, true);
        statusLine.addView(statusDot);
        statusTitle = label("Pronto para conectar", 16, ACCENT, true);
        LinearLayout.LayoutParams statusTitleParams = new LinearLayout.LayoutParams(0, -2, 1);
        statusTitleParams.leftMargin = dp(10);
        statusLine.addView(statusTitle, statusTitleParams);
        statusDetail = label("O microfone será transmitido para o seu PC quando você iniciar.", 13, MUTED, false);
        LinearLayout.LayoutParams statusDetailParams = matchWrap();
        statusDetailParams.leftMargin = dp(25);
        statusDetailParams.topMargin = dp(8);
        statusCard.addView(statusDetail, statusDetailParams);

        TextView footer = label("Wi-Fi: mesma rede local · USB: encaminhamento ADB\nAo iniciar, o serviço continua ativo com a tela bloqueada.", 12, MUTED, false);
        footer.setGravity(Gravity.CENTER);
        LinearLayout.LayoutParams footerParams = matchWrap();
        footerParams.topMargin = dp(20);
        page.addView(footer, footerParams);

        setContentView(scroll);
    }

    private Button modeButton(String text, boolean wifi) {
        Button button = new Button(this);
        button.setAllCaps(false);
        button.setText(text);
        button.setTextSize(15);
        button.setOnClickListener(v -> {
            wifiMode = wifi;
            getPreferences(MODE_PRIVATE).edit().putBoolean("wifi_mode", wifiMode).apply();
            updateModeButtons();
            updateAddress();
        });
        return button;
    }

    private void updateModeButtons() {
        styleModeButton(wifiButton, wifiMode);
        styleModeButton(usbButton, !wifiMode);
    }

    private void styleModeButton(Button button, boolean selected) {
        button.setTextColor(selected ? ACCENT : MUTED);
        button.setBackground(rounded(selected ? 0xff0b2927 : PANEL_ALT,
                selected ? ACCENT : BORDER, selected ? 2 : 1, 16));
    }

    private void updateAddress() {
        if (address == null) return;
        if (wifiMode) {
            address.setText("Wi-Fi: " + wifiIpv4() + "  ·  Porta " + PORT + "  ·  descoberta automática");
        } else {
            address.setText("USB: conecte e autorize o aparelho no Linux  ·  127.0.0.1:" + PORT);
        }
    }

    private String wifiIpv4() {
        String fallback = "endereço indisponível";
        try {
            Enumeration<NetworkInterface> interfaces = NetworkInterface.getNetworkInterfaces();
            while (interfaces != null && interfaces.hasMoreElements()) {
                NetworkInterface network = interfaces.nextElement();
                if (!network.isUp() || network.isLoopback()) continue;
                Enumeration<java.net.InetAddress> addresses = network.getInetAddresses();
                while (addresses.hasMoreElements()) {
                    java.net.InetAddress candidate = addresses.nextElement();
                    if (candidate instanceof Inet4Address && !candidate.isLoopbackAddress()) {
                        if (network.getName().startsWith("wlan")) return candidate.getHostAddress();
                        fallback = candidate.getHostAddress();
                    }
                }
            }
        } catch (Exception ignored) { }
        return fallback;
    }

    private void requestMicAndStart() {
        if (checkSelfPermission(Manifest.permission.RECORD_AUDIO) != PackageManager.PERMISSION_GRANTED) {
            requestPermissions(new String[]{Manifest.permission.RECORD_AUDIO}, PERMISSION_REQUEST);
            return;
        }
        startService();
    }

    private void startService() {
        Intent intent = new Intent(this, MicStreamService.class);
        intent.putExtra(MicStreamService.EXTRA_PORT, PORT);
        intent.putExtra(MicStreamService.EXTRA_WIFI_MODE, wifiMode);
        if (Build.VERSION.SDK_INT >= 26) startForegroundService(intent);
        else startService(intent);
        updateStatus("starting");
        Toast.makeText(this, "MICkz iniciado. Você pode bloquear a tela ou usar outros apps.", Toast.LENGTH_LONG).show();
    }

    private void stopMicrophone() {
        stopService(new Intent(this, MicStreamService.class));
        updateStatus("stopped");
    }

    private void refreshServiceState() {
        String state = getSharedPreferences(PREFS, MODE_PRIVATE).getString("service_state", "stopped");
        updateStatus(state);
        if (statusTitle != null && resumed && !isFinishing()) {
            statusTitle.postDelayed(this::refreshServiceState, 700);
        }
    }

    private void updateStatus(String state) {
        if (statusTitle == null) return;
        boolean active = !"stopped".equals(state) && !"error".equals(state);
        wifiButton.setEnabled(!active);
        usbButton.setEnabled(!active);
        wifiButton.setAlpha(active ? 0.55f : 1.0f);
        usbButton.setAlpha(active ? 0.55f : 1.0f);
        startButton.setEnabled(!active);
        startButton.setAlpha(active ? 0.55f : 1.0f);
        stopButton.setEnabled(active);
        stopButton.setAlpha(active ? 1.0f : 0.55f);
        if ("connected".equals(state)) {
            statusTitle.setText("Conectado ao PC");
            statusDetail.setText("Áudio do microfone está sendo transmitido.");
            statusTitle.setTextColor(ACCENT);
        } else if ("waiting".equals(state) || "starting".equals(state)) {
            statusTitle.setText("Aguardando conexão");
            statusDetail.setText(wifiMode ? "Inicie o receptor no PC para conectar automaticamente." : "Inicie o receptor USB no PC para conectar.");
            statusTitle.setTextColor(ACCENT);
        } else if ("error".equals(state)) {
            statusTitle.setText("Não foi possível iniciar");
            statusDetail.setText("Confira a notificação do MICkz e tente iniciar novamente.");
            statusTitle.setTextColor(0xffff947d);
        } else {
            statusTitle.setText("Pronto para conectar");
            statusDetail.setText("O microfone será transmitido para o seu PC quando você iniciar.");
            statusTitle.setTextColor(ACCENT);
        }
    }

    private GradientDrawable rounded(int color, int stroke, int strokeWidth, int radius) {
        GradientDrawable drawable = new GradientDrawable();
        drawable.setColor(color);
        drawable.setCornerRadius(dp(radius));
        if (strokeWidth > 0) drawable.setStroke(dp(strokeWidth), stroke);
        return drawable;
    }

    private TextView label(String text, int size, int color, boolean bold) {
        TextView view = new TextView(this);
        view.setText(text);
        view.setTextSize(size);
        view.setTextColor(color);
        if (bold) view.setTypeface(Typeface.DEFAULT, Typeface.BOLD);
        return view;
    }

    private LinearLayout.LayoutParams matchWrap() {
        return new LinearLayout.LayoutParams(-1, -2);
    }

    private int dp(int value) {
        return (int) (value * getResources().getDisplayMetrics().density + 0.5f);
    }

    @Override
    protected void onResume() {
        super.onResume();
        resumed = true;
        updateAddress();
        refreshServiceState();
    }

    @Override
    protected void onPause() {
        resumed = false;
        super.onPause();
    }

    @Override
    public void onRequestPermissionsResult(int requestCode, String[] permissions, int[] results) {
        super.onRequestPermissionsResult(requestCode, permissions, results);
        if (requestCode == PERMISSION_REQUEST && results.length > 0 && results[0] == PackageManager.PERMISSION_GRANTED) {
            startService();
        } else if (requestCode == PERMISSION_REQUEST) {
            Toast.makeText(this, "A permissão de microfone é necessária para transmitir áudio.", Toast.LENGTH_LONG).show();
        }
    }
}
