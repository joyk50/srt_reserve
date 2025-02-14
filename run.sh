#! /bin/bash
dpt=수서
arr=광주송정
dt=20250215
tm=10           # 두시간 간격으로 선택 가능
num=2

# .env 파일이 있는 경우 환경 변수를 설정합니다.
if [ -f .env ]; then
    # .env 파일 내에서 주석(#)을 제외한 라인을 읽어 환경 변수로 export 합니다.
    export $(grep -v '^#' .env | xargs)
fi

python3 quickstart.py --user ${user} --psw ${psw} --dpt ${dpt} --arr ${arr} --dt ${dt} --tm ${tm} --num ${num} --reserve True --token ${token} --chat_id ${chat_id}