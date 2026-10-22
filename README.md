# MICkz

Use o microfone de um celular Android como entrada de áudio no Linux. O app envia PCM mono, 48 kHz, 16 bits por TCP; o receptor injeta o áudio em uma fonte virtual PipeWire/PulseAudio.

## Requisitos

- CachyOS (ou outra distribuição com PipeWire e compatibilidade PulseAudio), Python 3, Tkinter e `pipewire-pulse` para a interface gráfica do Linux.
- `adb` (`android-tools` no CachyOS) para configurar a conexão USB pela interface.
- Android 8.0 (API 26) ou mais recente.
- Android Studio, Android SDK e JDK 17 para compilar o app. O projeto usa Android Gradle Plugin 8.13.2, compatível com Gradle 8.13. O receptor não usa dependências Python externas.

No Android Studio, abra **SDK Manager** e instale **Android SDK Platform 36** e **Android SDK Build-Tools 36.0.0**. Para instalar pelo terminal, depois de instalar o Android SDK Command-line Tools e aceitar as licenças, use `sdkmanager "platforms;android-36" "build-tools;36.0.0"`. O `compileSdk` deste projeto é 36.

Para compilar no Android Studio, abra a pasta `android/` e sincronize o projeto com Gradle 8.13. O Android Gradle Plugin 8.13.2 não funciona com Gradle 9.x. Se o Gradle instalado no sistema for 9.x, gere o wrapper em uma pasta temporária para não carregar o plugin Android durante essa etapa:

```bash
mkdir -p /tmp/mickz-wrapper-bootstrap
cd /tmp/mickz-wrapper-bootstrap
touch settings.gradle
gradle wrapper --gradle-version 8.13

cp gradlew gradlew.bat "$HOME/Documentos/ChatGPT/Projeto MICkz/android/"
mkdir -p "$HOME/Documentos/ChatGPT/Projeto MICkz/android/gradle/wrapper"
cp gradle/wrapper/gradle-wrapper.jar gradle/wrapper/gradle-wrapper.properties "$HOME/Documentos/ChatGPT/Projeto MICkz/android/gradle/wrapper/"

cd "$HOME/Documentos/ChatGPT/Projeto MICkz/android"
./gradlew assembleDebug
```

O wrapper baixa e executa o Gradle 8.13. O APK de depuração será salvo em `android/app/build/outputs/apk/debug/app-debug.apk`.

Se a compilação disser `SDK location not found`, indique a pasta real do SDK. O caminho padrão do Android Studio no Linux é `~/Android/Sdk`; confirme esse caminho no SDK Manager. Na pasta `android/`, rode `printf 'sdk.dir=%s\n' "$HOME/Android/Sdk" > local.properties` (ajuste o caminho se o SDK estiver em outro lugar) e tente `./gradlew assembleDebug` novamente. `local.properties` é uma configuração local da máquina.

## Instalar e conectar por USB

Ative as Opções do desenvolvedor e a depuração USB no Android. Conecte o celular, autorize a depuração quando solicitado e confirme que `adb devices` mostra o aparelho como `device`. Na raiz deste repositório, instale o APK:

```bash
adb install -r android/app/build/outputs/apk/debug/app-debug.apk
```

Instale e abra a interface gráfica Linux conforme a seção abaixo. Inicie o receptor, use **Configurar USB** e, no app Android, mantenha o host `127.0.0.1`. Autorize o microfone. No Linux, selecione `mickz_android_mic` (descrição `MICkz_Android_Microphone`) como entrada no Discord.

## Interface gráfica no CachyOS

Execute uma vez, na pasta do projeto, para instalar o MICkz no menu de aplicativos do seu usuário:

```bash
bash linux/install.sh
```

Depois, procure por **MICkz** no menu de aplicativos e abra-o como qualquer outro programa; não é necessário manter um terminal aberto. O instalador copia a interface e o receptor para `~/.local/share/mickz` e cria o lançador em `~/.local/share/applications`.

Na janela, clique em **Iniciar receptor** antes de conectar o celular. Para Wi-Fi, use o IP mostrado na janela no app Android. Para USB, conecte e autorize o telefone, clique em **Configurar USB** e use `127.0.0.1` no app. Os níveis de pico/RMS e as mensagens do receptor aparecem na área **Atividade**. **Parar receptor** remove a fonte virtual do sistema.

O app usa Tkinter, incluído em muitas instalações do Python. Se o instalador disser que Tkinter não está disponível, instale-o no CachyOS com `sudo pacman -S tk` e execute o instalador novamente. Para USB, instale também `sudo pacman -S android-tools` se `adb` não estiver disponível.

Para atualizar a cópia instalada depois de receber mudanças no projeto, execute novamente `bash linux/install.sh`.

## Receptor Linux e fonte de áudio

Instale ferramentas de áudio caso ainda não estejam disponíveis:

```bash
sudo pacman -S pipewire pipewire-pulse pipewire-audio pipewire-alsa
```

O jeito recomendado de iniciar o servidor é abrir **MICkz** pelo menu de aplicativos e clicar em **Iniciar receptor**. Para uso manual pelo terminal, o comando continua disponível:

```bash
python linux/mickz_receiver.py
```

O receptor abre a porta TCP `49152` em todas as interfaces e cria a fonte de entrada `mickz_android_mic` usando o módulo `module-pipe-source`. Se o firewall estiver ativo, permita a porta TCP 49152 na rede local. Ao parar pela interface, a fonte virtual é removida automaticamente.

Durante a conexão, a interface mostra os níveis de pico/RMS do áudio a cada dois segundos. Isso ajuda a distinguir silêncio vindo do celular de áudio que não chega à fonte virtual.

## Android por Wi-Fi

1. Conecte o computador e o celular à mesma rede local.
2. Descubra o IPv4 do computador com `ip -4 addr` (por exemplo, `192.168.1.20`).
3. Abra `android/` no Android Studio, compile e instale o app no celular.
4. No app, informe o IP do computador e toque em **Conectar**. Autorize o uso do microfone.

Para melhor latência, prefira Wi-Fi de 5 GHz e mantenha o celular perto do roteador.

## Android por USB

Ative a depuração USB no Android e conecte o cabo. Na interface Linux, inicie o receptor e clique em **Configurar USB**. No app Android use host `127.0.0.1` e toque em **Conectar**. O áudio passa pelo cabo USB; não é necessário compartilhar a rede Wi-Fi. Se preferir configurar manualmente, execute `adb reverse tcp:49152 tcp:49152` com o receptor ativo.

## Selecionar no Discord e nos jogos

Com o receptor e o app conectados, abra as configurações de áudio do Discord e selecione `mickz_android_mic` (descrição `MICkz_Android_Microphone`) como dispositivo de entrada. Se o Discord já estava aberto, reinicie-o para atualizar a lista. O mesmo dispositivo de entrada PipeWire aparece nos jogos que permitem escolher microfone.

Confira as fontes disponíveis com:

```bash
pactl list short sources
```

## Limites desta versão

- Esta versão mantém a captura ativa por um serviço em primeiro plano enquanto o app estiver conectado. O Android mostra uma notificação persistente.
- O transporte é PCM sem compressão, cerca de 768 kbit/s mais overhead. O protocolo não tem autenticação; use apenas em uma rede confiável ou por USB.
- O Android pode aplicar processamento ao microfone conforme o fabricante. O app usa `VOICE_RECOGNITION` para tentar reduzir esse processamento.
- Bluetooth, reconexão automática, controles de ganho e empacotamento de um APK ainda não fazem parte do protótipo.

## Solução de problemas

- Se o MICkz conecta, mas o nível de áudio fica zerado, feche outros apps que estejam capturando o microfone do Android (por exemplo, Audio Relay ou um gravador) e reconecte. A política de compartilhamento de entrada do Android pode entregar silêncio a um dos apps quando há disputa pelo microfone. [Documentação do Android sobre compartilhamento de entrada](https://developer.android.com/media/platform/sharing-audio-input).

## Estrutura

- `android/`: app Android nativo Java, sem bibliotecas de terceiros.
- `linux/mickz_gui.py`: interface gráfica para iniciar, parar e acompanhar o receptor.
- `linux/mickz_receiver.py`: servidor TCP e ponte PCM para PipeWire.
- `linux/install.sh`: instala o aplicativo no menu do desktop Linux.
