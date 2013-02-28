싱싱한 산낚지
===========

이 저장소는 LangDev 채널 로그 뷰어(<http://log.langdev.org/>) 서비스의
소스 코드를 담고 있습니다.


시작하기
--------

### 준비

LangDev 포럼에 접속 후, <http://langdev.org/apps/> 페이지에서 새로운
애플리케이션을 생성합니다. 발급받은 애플리케이션 키와 비밀키는
`logviewer/settings.py`에서 사용됩니다.

IRC 봇과 로그 뷰어가 사용할 로그 폴더를 만듭니다. 편의상 저장소 내의 `logs`
폴더라고 합시다.

### 개발환경 설치

IRC 로그 봇인 `bot.js`는 자바스크립트로 작성되어 [node.js][]를 통해 동작합니다.
사용하는 OS에 맞는 방법으로 [node.js][]를 설치하시고, [node.js][]의 패키징
시스템인 [npm][]도 함께 설치합니다. [npm][]은 *nix 환경에서 다음 명령으로
설치할 수 있습니다

    $ curl http://npmjs.org/install.sh | sh

[npm][]을 사용해서 `bot.js`가 필요로 하는 라이브러리들을 설치합니다.

    $ npm install socket.io

[node.js]: http://nodejs.org/
[npm]: http://npmjs.org/


[Python][]으로 작성된 로그 뷰어는 `logviewer` 폴더 내에 있는데, [Flask][]
프레임워크를 사용한 웹 애플리케이션으로 되어 있습니다. [virtualenv][]와
[distribute][] 및 [pip][]을 사용하시면 개발환경 설정에 도움이 됩니다. 자세한
설정법은 다음 게시물을 참고하십시오. <http://yong27.biohackers.net/373>

[pip][]을 사용한다고 가정했을 때, 다음 명령으로 필요한 모든 라이브러리를 설치할
수 있습니다.

    $ pip install -e .
    # 또는 pip 없이 이렇게도 할 수 있습니다.
    $ python setup.py develop

[Python]: http://python.org/
[Flask]: http://flask.pocoo.org/
[virtualenv]: http://pypi.python.org/pypi/virtualenv
[distribute]: http://pypi.python.org/pypi/distribute
[pip]: http://pypi.python.org/pypi/pip

### 설정

`config.js.sample`파일을 복사하여 `config.js`를 만들고, 주석을 참조하여 필요한
내용들을 수정하십시오. 마찬가지로 `logviewer/settings.py.sample` 파일을
복사하여 `logviewer/settings.py` 파일을 만들고 내용을 수정하십시오. LangDev
포럼에서 받은 애플리케이션 키를 여기에 넣습니다.

### 로그 수집

로그 뷰어를 실행하기 위해서는 먼저 로그 봇을 실행하여 IRC 로그를 수집해야
합니다.

    $ node bot.js
       info  - socket.io started

### 로그 뷰어(웹서버) 실행

로그가 어느 정도 쌓이고 나면 이제 다음 명령으로 웹서버를 실행할 수 있습니다.

    $ LOGVIEWER_SETTINGS="logviewer/settings.py" python logviewer/app.py
     * Running on http://0.0.0.0:5000/
     * Restarting with reloader

이제 <http://localhost:5000/>과 같은 주소로 접속하면 로그 뷰어를 볼 수
있습니다.
