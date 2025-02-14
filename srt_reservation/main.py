# -*- coding: utf-8 -*-
import os
import time
from random import uniform 
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.by import By
from selenium.common.exceptions import ElementClickInterceptedException, StaleElementReferenceException, WebDriverException

from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

import asyncio
from aiogram import Bot, Dispatcher

from srt_reservation.exceptions import InvalidStationNameError, InvalidDateError, InvalidDateFormatError
from srt_reservation.validation import station_list

chromedriver_path = r'/opt/homebrew/bin/chromedriver'

class SRT:
    def __init__(self, dpt_stn, arr_stn, dpt_dt, dpt_tm, num_trains_to_check=2, want_reserve=False,
                 token=None, chat_id=None):
        """
        :param dpt_stn: SRT 출발역
        :param arr_stn: SRT 도착역
        :param dpt_dt: 출발 날짜 YYYYMMDD 형태 ex) 20220115
        :param dpt_tm: 출발 시간 hh 형태, 반드시 짝수 ex) 06, 08, 14, ...
        :param num_trains_to_check: 검색 결과 중 예약 가능 여부 확인할 기차의 수 (예: 상위 2개 기차)
        :param want_reserve: 예약 대기가 가능할 경우 선택 여부
        """
        self.login_id = None
        self.login_psw = None

        self.dpt_stn = dpt_stn
        self.arr_stn = arr_stn
        self.dpt_dt = dpt_dt
        self.dpt_tm = dpt_tm

        self.num_trains_to_check = num_trains_to_check
        self.want_reserve = want_reserve
        self.driver = None

        self.is_booked = False  # 예약 완료 여부 확인용
        self.cnt_refresh = 0    # 새로고침 회수 기록

        self.check_input()
        
        self.token = token
        self.chat_id = chat_id

        # aiogram Bot 및 Dispatcher 객체 초기화
        if self.token is not None and self.chat_id is not None:
            self.bot = Bot(token=self.token)
            self.dp = Dispatcher()

    def check_input(self):
        if self.dpt_stn not in station_list:
            raise InvalidStationNameError(f"출발역 오류. '{self.dpt_stn}' 은/는 목록에 없습니다.")
        if self.arr_stn not in station_list:
            raise InvalidStationNameError(f"도착역 오류. '{self.arr_stn}' 은/는 목록에 없습니다.")
        if not str(self.dpt_dt).isnumeric():
            raise InvalidDateFormatError("날짜는 숫자로만 이루어져야 합니다.")
        try:
            datetime.strptime(str(self.dpt_dt), '%Y%m%d')
        except ValueError:
            raise InvalidDateError("날짜가 잘못 되었습니다. YYYYMMDD 형식으로 입력해주세요.")

    def set_log_info(self, login_id, login_psw):
        self.login_id = login_id
        self.login_psw = login_psw

    def run_driver(self):
        """
        ChromeDriverManager를 사용하여 크롬 드라이버를 실행하는 메서드.
        크롬 실행 파일 경로(binary_location)와 추가 옵션들을 지정합니다.
        """
        options = webdriver.ChromeOptions()
        # 크롬 실행 파일 위치 지정 (환경에 맞게 수정하세요)
        options.binary_location = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
        # 필요에 따라 헤드리스 모드 활성화 (테스트 시 주석 해제)
        # options.add_argument('--headless')
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--disable-gpu')
        options.add_argument('--remote-debugging-port=9222')
        
        # ChromeDriverManager를 사용하여 자동으로 드라이버 설치 후 Service 객체를 생성합니다.
        from selenium.webdriver.chrome.service import Service  # Service 클래스 임포트
        from webdriver_manager.chrome import ChromeDriverManager
        service = Service(ChromeDriverManager().install())
        
        try:
            self.driver = webdriver.Chrome(service=service, options=options)
        except WebDriverException as e:
            print(f"Chrome 드라이버 실행중 오류 발생: {e}")
            raise

    def login(self):
        self.driver.get('https://etk.srail.co.kr/cmc/01/selectLoginForm.do')
        self.driver.implicitly_wait(15)
        self.driver.find_element(By.ID, 'srchDvNm01').send_keys(str(self.login_id))
        self.driver.find_element(By.ID, 'hmpgPwdCphd01').send_keys(str(self.login_psw))
        self.driver.find_element(By.XPATH, '//*[@id="login-form"]/fieldset/div[1]/div[1]/div[2]/div/div[2]/input').click()
        self.driver.implicitly_wait(5)
        return self.driver

    def check_login(self):
        menu_text = self.driver.find_element(By.CSS_SELECTOR, "#wrap > div.header.header-e > div.global.clear > div").text
        if "환영합니다" in menu_text:
            return True
        else:
            return False

    def go_search(self):
        # 기차 조회 페이지로 이동
        self.driver.get('https://etk.srail.kr/hpg/hra/01/selectScheduleList.do')
    
        # 최대 10초동안 출발역 입력창이 나타날 때까지 기다립니다.
        wait = WebDriverWait(self.driver, 10)
        try:
            elm_dpt_stn = wait.until(EC.presence_of_element_located((By.ID, 'dptRsStnCdNm')))
        except Exception as e:
            print("출발역 입력창 로딩 실패:", e)
            raise

        # 요소를 찾았으면 동작 진행
        elm_dpt_stn.clear()
        elm_dpt_stn.send_keys(self.dpt_stn)

        # 도착역 입력
        try:
            elm_arr_stn = wait.until(EC.presence_of_element_located((By.ID, 'arvRsStnCdNm')))
        except Exception as e:
            print("도착역 입력창 로딩 실패:", e)
            raise

        elm_arr_stn.clear()
        elm_arr_stn.send_keys(self.arr_stn)

        # 출발 날짜 입력
        try:
            elm_dpt_dt = wait.until(EC.presence_of_element_located((By.ID, "dptDt")))
        except Exception as e:
            print("날짜 선택 요소 로딩 실패:", e)
            raise

        # 날짜 선택 요소가 숨김 상태일 수 있으므로 스크립트를 통해 보이게끔 변경
        self.driver.execute_script("arguments[0].setAttribute('style','display: block;')", elm_dpt_dt)
        from selenium.webdriver.support.ui import Select
        Select(elm_dpt_dt).select_by_value(self.dpt_dt)

        # 출발 시간 입력
        try:
            elm_dpt_tm = wait.until(EC.presence_of_element_located((By.ID, "dptTm")))
        except Exception as e:
            print("시간 선택 요소 로딩 실패:", e)
            raise

        self.driver.execute_script("arguments[0].setAttribute('style','display: block;')", elm_dpt_tm)
        Select(elm_dpt_tm).select_by_visible_text(self.dpt_tm)

        print("기차를 조회합니다")
        print(f"출발역: {self.dpt_stn} , 도착역: {self.arr_stn}\n날짜: {self.dpt_dt}, 시간: {self.dpt_tm}시 이후\n{self.num_trains_to_check}개의 기차 중 예약")
        print(f"예약 대기 사용: {self.want_reserve}")

        # '조회하기' 버튼 클릭
        try:
            search_btn = wait.until(EC.element_to_be_clickable((By.XPATH, "//input[@value='조회하기']")))
            search_btn.click()
        except Exception as e:
            print("조회 버튼 클릭 실패:", e)
            raise

        # 페이지 안정화를 위해 잠시 대기
        self.driver.implicitly_wait(5)
        import time
        time.sleep(1)

    def book_ticket(self, standard_seat, i):
        # standard_seat: 일반석 검색 결과 텍스트
        if "예약하기" in standard_seat:
            print("예약 가능 클릭")
            try:
                self.driver.find_element(By.CSS_SELECTOR,
                                         f"#result-form > fieldset > div.tbl_wrap.th_thead > table > tbody > tr:nth-child({i}) > td:nth-child(7) > a").click()
            except ElementClickInterceptedException as err:
                print(err)
                self.driver.find_element(By.CSS_SELECTOR,
                                         f"#result-form > fieldset > div.tbl_wrap.th_thead > table > tbody > tr:nth-child({i}) > td:nth-child(7) > a").send_keys(
                    Keys.ENTER)
            finally:
                self.driver.implicitly_wait(3)

            if self.driver.find_elements(By.ID, 'isFalseGotoMain'):
                self.is_booked = True
                print("예약 성공")
                return self.driver
            else:
                print("잔여석 없음. 다시 검색")
                self.driver.back()  # 이전 페이지로 이동
                self.driver.implicitly_wait(5)

    def refresh_result(self):
        submit = self.driver.find_element(By.XPATH, "//input[@value='조회하기']")
        self.driver.execute_script("arguments[0].click();", submit)
        self.cnt_refresh += 1
        print(f"새로고침 {self.cnt_refresh}회")
        self.driver.implicitly_wait(10)
        time.sleep(uniform(0.5, 2.0))
        
    def reserve_ticket(self, reservation, i):
        if "신청하기" in reservation:
            print("예약 대기 완료")
            self.driver.find_element(By.CSS_SELECTOR,
                                     f"#result-form > fieldset > div.tbl_wrap.th_thead > table > tbody > tr:nth-child({i}) > td:nth-child(8) > a").click()
            self.is_booked = True
            return self.is_booked

    def check_result(self):
        while True:
            for i in range(1, self.num_trains_to_check+1):
                try:
                    standard_seat = self.driver.find_element(By.CSS_SELECTOR, f"#result-form > fieldset > div.tbl_wrap.th_thead > table > tbody > tr:nth-child({i}) > td:nth-child(7)").text
                    reservation = self.driver.find_element(By.CSS_SELECTOR, f"#result-form > fieldset > div.tbl_wrap.th_thead > table > tbody > tr:nth-child({i}) > td:nth-child(8)").text
                except StaleElementReferenceException:
                    standard_seat = "매진"
                    reservation = "매진"

                if self.book_ticket(standard_seat, i):
                    return self.driver

                if self.want_reserve:
                    self.reserve_ticket(reservation, i)

            if self.is_booked:
                return self.driver
            else:
                time.sleep(uniform(2.0, 4.0))
                self.refresh_result()

    def run(self, lgn_id, lgn_psw):
        # aiogram을 사용하여 main 함수의 비동기 실행
        asyncio.run(self.main(lgn_id, lgn_psw))
        
    async def main(self, lgn_id, lgn_psw):
        # 예약 시작 전 텔레그램 메시지 전송 (aiogram 사용)
        start_text = f"SRT 예약을 시도합니다:\n  {self.dpt_stn} -> {self.arr_stn}\n날짜: {self.dpt_dt}, 시간: {self.dpt_tm}시 이후\n"
        start_text += f"{self.num_trains_to_check}개의 기차 중 예약\n예약 대기 사용: {self.want_reserve}"
        await self.bot.send_message(chat_id=self.chat_id, text=start_text)
        
        # blocking 작업들을 별도의 스레드에서 실행하여 이벤트 루프 차단 방지 (Python 3.9 이상의 asyncio.to_thread 사용)
        await asyncio.to_thread(self.run_driver)
        self.set_log_info(lgn_id, lgn_psw)
        await asyncio.to_thread(self.login)
        await asyncio.to_thread(self.go_search)
        await asyncio.to_thread(self.check_result)

        # 예약 완료 후 텔레그램 메시지 전송
        await self.bot.send_message(chat_id=self.chat_id, text="SRT 승차권이 예약되었습니다. 결재를 진행해 주세요")