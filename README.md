# MICkz

Use o microfone de um celular Android como entrada de áudio no Linux. O Android aguarda a conexão e o MICkz no Linux inicia uma conexão TCP de saída; o PC não precisa abrir portas nem alterar regras do firewall. O áudio é PCM mono, 48 kHz, 16 bits, injetado em uma fonte virtual PipeWire/PulseAudio.

## Requisitos

- Linux com PipeWire e compatibilidade PulseAudio, Python 3, Tkinter, `pactl` e `ip`.
- `adb` (`android-tools` no CachyOS) para configurar a conexão USB pela interface; é opcional para Wi-Fi.
- Android 8.0 (API 26) ou mais recente.
- Android Studio, Android SDK e JDK 17 para compilar o app. O projeto usa Android Gradle Plugin 8.13.2, compatível com Gradle 8.13. O receptor não usa dependências Python externas.

## Instalação rápida

Baixe o código-fonte ZIP da versão `v0.4.0` na seção **Releases** do GitHub, extraia e instale para seu usuário:

```bash
unzip MICkz-0.4.0.zip
cd MICkz-0.4.0
bash linux/install.sh
```

No CachyOS/Arch, instale as dependências do sistema antes de executar o instalador:

```bash
sudo pacman -S python tk pipewire-pulse iproute2
```

Para USB, instale também `sudo pacman -S android-tools`. Em outras distribuições, instale Python 3 com Tkinter, PipeWire com compatibilidade PulseAudio e `iproute2` usando os pacotes equivalentes. O instalador verifica Python/Tkinter, `pactl` e `ip`, copia os arquivos para `~/.local/share/mickz` e cria o lançador no menu do usuário. Ele não precisa de `sudo`.

Também é possível clonar o repositório e executar `bash linux/install.sh` na raiz. Depois, procure **MICkz** no menu de aplicativos.

## Instalação do app Android

Baixe `MICkz-0.4.0-android.apk` na seção **Releases**. Instale pelo Android abrindo o arquivo APK e autorizando a instalação para o app de arquivos/navegador, ou use ADB:

```bash
adb install -r MICkz-0.4.0-android.apk
```

O APK do release é uma compilação de depuração assinada com chave debug, indicada para testes e instalação manual; não é uma versão publicada na Play Store.

## Compilar o app Android

No Android Studio, abra a pasta `android/` e instale **Android SDK Platform 36** e **Android SDK Build-Tools 36.0.0** pelo SDK Manager. O projeto inclui o Gradle Wrapper 8.13, então não é necessário instalar Gradle globalmente nem gerar um wrapper. Com o Android SDK instalado, compile assim:

```bash
cd android
./gradlew assembleDebug
```

O APK será salvo em `android/app/build/outputs/apk/debug/app-debug.apk`. Se o Gradle não localizar o SDK, crie `android/local.properties` com `sdk.dir=/caminho/para/Android/Sdk`; esse arquivo é local e não deve ser enviado ao GitHub.

Se a compilação disser `SDK location not found`, indique a pasta real do SDK. O caminho padrão do Android Studio no Linux é `~/Android/Sdk`; confirme esse caminho no SDK Manager. Na pasta `android/`, rode `printf 'sdk.dir=%s\n' "$HOME/Android/Sdk" > local.properties` (ajuste o caminho se o SDK estiver em outro lugar) e tente `./gradlew assembleDebug` novamente. `local.properties` é uma configuração local da máquina.

## Instalar e conectar por USB

Ative as Opções do desenvolvedor e a depuração USB no Android. Conecte o celular, autorize a depuração quando solicitado e confirme que `adb devices` mostra o aparelho como `device`. Na raiz deste repositório, instale o APK:

```bash
adb install -r android/app/build/outputs/apk/debug/app-debug.apk
```

Instale e abra a interface gráfica Linux conforme a seção abaixo. Para USB, use **Configurar USB** na interface Linux e selecione **USB** no app Android. Autorize o microfone. No Linux, selecione `mickz_android_mic` (descrição `MICkz_Android_Microphone`) como entrada no Discord.

## Interface gráfica no CachyOS

Execute uma vez, na pasta extraída do projeto, para instalar o MICkz no menu de aplicativos do seu usuário:

```bash
bash linux/install.sh
```

Depois, procure por **MICkz** no menu de aplicativos e abra-o como qualquer outro programa; não é necessário manter um terminal aberto. O instalador copia a interface e o receptor para `~/.local/share/mickz` e cria o lançador em `~/.local/share/applications`.

Minimizar a janela pelo botão **–** mantém o MICkz na barra de tarefas e deixa o receptor e o áudio ativos. Fechar pelo botão **X** ou escolher **MICkz → Encerrar MICkz** encerra o receptor e o aplicativo. O botão **Parar** encerra somente o receptor; o aplicativo gráfico continua aberto.

No Android, toque em **Iniciar microfone**. No Linux, selecione **Wi-Fi automático** e clique em **Iniciar receptor**; o telefone será localizado na rede sem digitar IP. Para USB, conecte e autorize o telefone, clique em **Configurar USB** no Linux, selecione **USB** no Android e inicie o microfone; o Linux usará `127.0.0.1`. O Linux inicia somente conexões de saída, sem pedir alteração de regras no firewall. A barra mostra o nível de áudio recebido e um único indicador alterna entre conectado e desconectado. **Parar** remove a fonte virtual do sistema.

O app usa Tkinter e `iproute2` para localizar as sub-redes da máquina; ambos normalmente já estão instalados no CachyOS. Se o instalador disser que Tkinter não está disponível, instale-o com `sudo pacman -S tk`. Para USB, instale também `sudo pacman -S android-tools` se `adb` não estiver disponível.

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

O receptor cria a fonte de entrada `mickz_android_mic` com `module-pipe-source` e procura o servidor TCP do Android na porta `49152`. A busca usa conexões TCP de saída com uma mensagem de identificação; ela não ativa a captura de áudio até o Linux iniciar a conexão de transmissão. O PC não escuta conexões de entrada e não exige exceção de firewall. Ao parar pela interface, a fonte virtual é removida automaticamente.

Durante a conexão, a interface mostra os níveis de pico/RMS do áudio a cada dois segundos. Isso ajuda a distinguir silêncio vindo do celular de áudio que não chega à fonte virtual.

## Android por Wi-Fi

1. Conecte o computador e o celular à mesma rede Wi-Fi (não precisa conectar o cabo USB).
2. Na interface MICkz Linux, selecione **Wi-Fi automático** e clique em **Iniciar receptor**. A janela mostrará **Procurando celular…**.
3. No Android, selecione **Wi-Fi (sem cabo)** e toque em **Iniciar microfone**. Autorize o acesso ao microfone.
4. O telefone aparecerá na interface Linux como conectado; o MICkz mantém a busca ativa para reconectar se a ligação cair.

Para melhor latência, prefira Wi-Fi de 5 GHz e mantenha o celular perto do roteador.

## Android por USB

Ative a depuração USB no Android e conecte o cabo. Inicie o microfone no app Android e, na interface Linux, clique em **Configurar USB**. O MICkz configura `adb forward` para que o Linux conecte ao servidor do telefone em `127.0.0.1:49152`. Se preferir configurar manualmente, execute `adb forward tcp:49152 tcp:49152`. Não é necessário compartilhar a rede Wi-Fi.

## Selecionar no Discord e nos jogos

Com o receptor e o app conectados, abra as configurações de áudio do Discord e selecione `mickz_android_mic` (descrição `MICkz_Android_Microphone`) como dispositivo de entrada. Se o Discord já estava aberto, reinicie-o para atualizar a lista. O mesmo dispositivo de entrada PipeWire aparece nos jogos que permitem escolher microfone.

Confira as fontes disponíveis com:

```bash
pactl list short sources
```

## Execução em segundo plano

No Android, inicie o microfone enquanto o app estiver aberto e com a permissão de microfone concedida. A captura roda em um serviço de primeiro plano com notificação persistente e bloqueios de CPU/Wi-Fi durante a transmissão, então pode continuar com a tela bloqueada ou enquanto você usa outro app. Isso aumenta o consumo de bateria. Use **Parar microfone** para liberar esses recursos. O Android ainda pode interromper o serviço em situações como encerramento forçado pelo usuário, reinicialização do aparelho ou políticas específicas do fabricante; depois disso, abra o MICkz e inicie novamente.

No Linux, minimizar a janela mantém o processo ativo na barra de tarefas. Fechar a janela encerra o MICkz e o receptor.

## Limites desta versão

- Esta versão mantém a captura ativa por um serviço em primeiro plano enquanto o app estiver ativo. O Android mostra uma notificação persistente.
- O transporte é PCM sem compressão, cerca de 768 kbit/s mais overhead. O protocolo não tem autenticação; use apenas em uma rede confiável ou por USB.
- O Android pode aplicar processamento ao microfone conforme o fabricante. O app usa `VOICE_RECOGNITION` para tentar reduzir esse processamento.
- Bluetooth e controles de ganho ainda não fazem parte desta versão.

## Solução de problemas

- Se o MICkz conecta, mas o nível de áudio fica zerado, feche outros apps que estejam capturando o microfone do Android (por exemplo, Audio Relay ou um gravador) e reconecte. A política de compartilhamento de entrada do Android pode entregar silêncio a um dos apps quando há disputa pelo microfone. [Documentação do Android sobre compartilhamento de entrada](https://developer.android.com/media/platform/sharing-audio-input).
- Se o Linux não encontrar o celular, confirme que o receptor está buscando, que o serviço MICkz está ativo no Android e que ambos estão na mesma rede local, sem isolamento entre clientes. A descoberta usa a sub-rede IPv4 da interface local; não é necessário digitar o IP nem abrir uma porta de entrada no firewall do PC.

## Estrutura

- `android/`: app Android nativo Java, sem bibliotecas de terceiros.
- `linux/mickz_gui.py`: interface gráfica para iniciar, parar e acompanhar o receptor.
- `linux/mickz_receiver.py`: cliente TCP e ponte PCM para PipeWire.
- `linux/install.sh`: instala o aplicativo no menu do desktop Linux.
