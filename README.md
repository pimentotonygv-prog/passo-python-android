# Passo Python — projeto Android

Reimplementação do Passo em Python com Kivy, mapa OpenStreetMap, GPS Android e serviço de gravação separado da interface.

Atualização da compilação: a primeira execução no GitHub passou nos 11 testes e compilou os componentes nativos, mas falhou ao reutilizar o ambiente de instalação de pacotes entre as arquiteturas. O projeto agora inclui uma correção pequena em `tools/prepare_p4a.py`, que recria esse ambiente a cada arquitetura, além de fixar uma versão puramente Python de chardet. O fluxo salva cache de compilação e um relatório separado em caso de falha. O fluxo também inicia automaticamente quando há envio à branch main. O resultado final da compilação será informado junto do APK; as limitações abaixo descrevem a entrega inicial do código.

## Estado da entrega 2.0.2

- APK 2.0.2 compilado e assinado com a mesma chave local da entrega 2.0.1. Pode ser instalado sobre o APK 2.0.1 enviado no chat, preservando os dados.
- Tela principal, Historico e Sobre com rolagem vertical por toque e barra de rolagem.
- Textos e botoes ajustam a altura ao conteudo e a largura disponivel. O mapa ajusta sua altura ao tamanho da janela.
- O mapa na pagina permite rolar a tela. Explorar mapa abre a visualizacao interativa, com retorno para a atividade.
- Os botoes de atividade nao sao recriados a cada atualizacao do cronometro.
- 16 testes da logica e do mapa passaram.
- Testes visuais e gestos de toque passaram em 280x480, 320x568, 360x640, 400x850 e 640x360, incluindo acesso ao ultimo botao, textos longos, ocultar/mostrar mapa e navegacao.
- Validacao executada em Kivy/Linux/Xvfb; as medidas sao janelas de teste, nao aparelhos fisicos Android.
- Compilacao: https://github.com/pimentotonygv-prog/passo-python-android/actions/runs/43545230863

### Assinatura e dados

A chave estavel usada para assinar o APK entregue fica apenas no computador do proprietario. Ela nao e publicada no projeto ou no GitHub. APKs brutos do GitHub usam uma chave temporaria diferente; para atualizar mantenha a mesma chave da instalacao.

A atualizacao 2.0.1 para 2.0.2 enviada neste chat preserva o historico ao instalar por cima, sem desinstalar. A versao antiga 2.0.0 usava outra assinatura: exporte GPX antes de remove-la caso ainda esteja usando essa versao. O Passo original em Java e um app separado.

## Funções implementadas no código

- Caminhada e corrida; peso entre 20 e 300 kg.
- Tempo ativo, distância, calorias estimadas, ritmo e velocidade média.
- Iniciar, pausar, retomar, finalizar e salvar.
- Mapa com linha do percurso, indicação da última posição, arrastar/zoom e centralizar.
- Abrir/fechar mapa GPS sem interromper a gravação; preferência persistida.
- Serviço Android foreground com notificação, listener GPS e bloqueio parcial de suspensão durante o registro.
- Histórico local SQLite, consulta do percurso, confirmação para apagar e exportação GPX pelo seletor de arquivos Android.
- Recuperação do último estado após interrupção, sem acrescentar o tempo em que o serviço ficou desligado.

## Precisão do GPS

O serviço solicita posições a cada segundo. O sistema pode entregá-las com outra frequência. São rejeitados pontos com precisão estimada pior que 15 metros, idade acima de 5 segundos, coordenadas inválidas e saltos incompatíveis com caminhada/corrida. O filtro evita parte da deriva quando parado e mantém passos curtos para preservar curvas.

Intervalos maiores que 8 segundos entre pontos aceitos criam outro segmento. Esse intervalo não ganha linha reta nem distância inventada. Pausar/retomar também separa segmentos. Os testes simulam uma esquina, salto de posição, sinal ruim, perda de sinal e recuperação.

**Não há ajuste automático às ruas (map matching).** A linha representa medições do GPS; não se pode garantir que fique sobre a rua em sinal ruim. Python por si só não aumenta a precisão. Não foram corrigidos os percursos antigos.

## App separado e dados

O pacote será `br.com.passo.python`, com nome **Passo Python**, diferente de `br.com.passo.app`. Pode ser instalado junto do original quando o APK estiver disponível. Esta versão não importa automaticamente seu histórico do app original. Exporte as atividades do original em GPX antes de removê-lo.

Não há conta ou servidor de trajetos. O mapa precisa de internet e solicita imagens ao OpenStreetMap, que recebe IP e área visualizada. O GPS registra sem internet; imagens não carregadas anteriormente podem ficar indisponíveis. O cache de mapas é apenas o cache normal da biblioteca, sem download em massa.

## Arquivos

| Arquivo | Função |
| --- | --- |
| `main.py` | Interface Kivy, navegação, mapa e controles |
| `passo/core.py` | GPS, distância, tempo, estimativas e GPX |
| `passo/storage.py` | SQLite e comunicação UI/serviço |
| `passo/android_bridge.py` | Permissões, início do serviço e seletor GPX |
| `service/tracking.py` | Serviço Python com GPS Android |
| `buildozer.spec` | Configuração de APK e permissões |
| `tests/test_core.py` | Testes independentes de Android |
| `.github/workflows/android.yml` | Compilação manual no GitHub Actions |

## Testar a lógica

Não precisa de Kivy para executar os testes:

```sh
python -m unittest discover -s tests -v
```

## Prévia da interface no computador

Use um ambiente virtual Python compatível com os pacotes Kivy disponíveis (3.11/3.12 são opções para a prévia). Na pasta do projeto:

```sh
python -m pip install -r requirements-desktop.txt
python main.py
```

A prévia não simula GPS nem grava atividades. O acesso real à localização usa recursos Android via PyJNIus.

## Gerar APK em Linux/WSL2

Use Ubuntu e Java 17. No Windows, o Buildozer exige WSL2; copie o projeto para o sistema de arquivos Linux antes da compilação. A configuração usa python-for-android `v2026.05.09` (receita Python 3.14.2), API Android 36 e NDK 28c. Use Python 3.14 no ambiente de compilação. O Buildozer e suas dependências ainda não estão congelados por hash; uma primeira compilação bem-sucedida deverá registrar as versões efetivas.

Instale os pacotes de sistema de acordo com a [documentação oficial do Buildozer](https://buildozer.readthedocs.io/en/latest/installation/), incluindo git, zip/unzip, Java 17, autoconf, automake, libtool, pkg-config, cmake e bibliotecas de desenvolvimento indicadas para sua versão do Ubuntu. Em um ambiente virtual Python 3.14:

```sh
python -m pip install git+https://github.com/kivy/buildozer setuptools legacy-cgi 'cython==0.29.34'
bash build-android.sh
```

O Buildozer baixa SDK/NDK e dependências e solicita aceitar as licenças Android. Ao terminar com sucesso, o APK de teste estará em `bin/`. A primeira compilação pode ser demorada e exigir ajustes conforme o ambiente. Nenhuma etapa desta compilação foi executada nesta entrega.

## Alternativa: GitHub Actions

O fluxo incluído só roda manualmente. Não foi publicado nem executado nesta entrega.

1. Coloque o conteúdo desta pasta na raiz de um repositório seu no GitHub, incluindo `.github`.
2. Abra **Actions → Gerar APK Android → Run workflow**.
3. Esse fluxo instala as ferramentas e aceita as licenças SDK como parte do comando de compilação. Execute apenas se concordar com elas.
4. Se a compilação terminar com sucesso, baixe o artefato **Passo-Python-APK** e extraia o APK.

Esse é um APK de teste, assinado com chave de depuração do ambiente. Novas execuções do GitHub podem gerar outra chave; para atualizações permanentes é necessário configurar uma chave de assinatura estável. Nenhuma chave privada do app original foi incluída.

## Validação que falta no celular

Antes de tratar esta versão como pronta para uso diário:

1. Compilar e instalar em Android 8 ou superior, sem remover o app original.
2. Conferir localização precisa, localização desligada e permissão negada.
3. Fazer uma caminhada com esquinas e comparar o traçado ao percurso real.
4. Apagar a tela por alguns minutos e conferir GPS, tempo e notificação.
5. Pausar, mudar de posição e retomar: não deve ligar os trechos.
6. Abrir/fechar mapa durante gravação e navegar ao histórico.
7. Finalizar, reabrir o app, exportar GPX, conferir o arquivo e apagar uma atividade.
8. Interromper o processo e conferir recuperação sem acrescentar tempo ou distância sem registro.

## Referências técnicas

- [Serviços Python Android e tipo foreground de localização](https://python-for-android.readthedocs.io/en/v2026.05.09/services.html).
- [Receita Python da versão usada na configuração](https://github.com/kivy/python-for-android/blob/v2026.05.09/pythonforandroid/recipes/python3/__init__.py).
- [Kivy Garden MapView](https://github.com/kivy-garden/mapview).
- [Requisitos de serviços foreground Android](https://developer.android.com/develop/background-work/services/fgs/launch).

Calorias usam a mesma fórmula do Passo anterior: 3,8 MET para caminhada e 7,5 MET para corrida. São estimativas pelo peso e tempo, não medição direta.
