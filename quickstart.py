""" Quickstart script for InstaPy usage """

import sys
from srt_reservation.main import SRT
from srt_reservation.util import parse_cli_args

if __name__ == "__main__":
    cli_args = parse_cli_args()

    login_id = cli_args.user
    login_psw = cli_args.psw
    dpt_stn = cli_args.dpt
    arr_stn = cli_args.arr
    dpt_dt = cli_args.dt
    dpt_tm = cli_args.tm

    num_trains_to_check = cli_args.num
    want_reserve = cli_args.reserve

    token = cli_args.token
    chat_id = cli_args.chat_id
    
    try:
        srt = SRT(dpt_stn, arr_stn, dpt_dt, dpt_tm, num_trains_to_check, want_reserve,
                  token=token, chat_id=chat_id)
        srt.run(login_id, login_psw)
    except KeyboardInterrupt:
        print("키보드 인터럽트가 발생하여 프로그램을 종료합니다.")
        if hasattr(srt, 'driver') and srt.driver:
            srt.driver.quit()
        sys.exit(0)