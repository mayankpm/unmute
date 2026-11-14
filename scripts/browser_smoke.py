"""Real browser integration checks using an isolated SQLite database and fake webcam.
Run: .venv/bin/python scripts/browser_smoke.py
Requires Playwright; uses installed Google Chrome. No patient data is modified.
"""
from pathlib import Path
import sys
import tempfile
import threading
import os
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from server import App, Handler, ThreadingHTTPServer
from playwright.sync_api import sync_playwright, expect


def main():
    root=Path(__file__).resolve().parents[1]
    artifacts=root/'artifacts'
    artifacts.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        # This test uses only local functionality, regardless of shell credentials.
        os.environ.pop('UNMUTE_TOKEN',None)
        os.environ.pop('MONGODB_URI',None)
        os.environ.pop('GEMINI_API_KEY',None)
        server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
        server.daemon_threads=True
        server.app=App(Path(tmp)/'test.db')
        threading.Thread(target=server.serve_forever,daemon=True).start()
        url=f'http://127.0.0.1:{server.server_port}'
        try:
            with sync_playwright() as p:
                browser=p.chromium.launch(channel='chrome',headless=True,args=[
                    '--use-fake-ui-for-media-stream','--use-fake-device-for-media-stream'])
                context=browser.new_context(viewport={'width':1440,'height':1150},permissions=['camera'])
                page=context.new_page()
                page.add_init_script('''
                  window.serialWrites=[];
                  let input;
                  const port={
                    readable:new ReadableStream({start(c){input=c;}}),
                    writable:new WritableStream({write(data){window.serialWrites.push(new TextDecoder().decode(data));}}),
                    open:async()=>{},close:async()=>{}
                  };
                  window.deviceInput=line=>input.enqueue(new TextEncoder().encode(line+'\\n'));
                  Object.defineProperty(navigator,'serial',{value:{requestPort:async()=>port},configurable:true});
                ''')
                errors=[]
                page.on('pageerror',lambda error:errors.append(str(error)))
                page.goto(url)
                expect(page.get_by_text('Local server connected',exact=True)).to_be_visible()
                expect(page.locator('.phrase-button')).to_have_count(12)
                page.screenshot(path=str(artifacts/'patient-desktop.png'),full_page=True)
                page.locator('[data-view="settings"]').click()
                page.locator('#check-gemini').click()
                expect(page.locator('#integration-check-results')).to_contain_text('Set GEMINI_API_KEY')
                page.locator('#check-atlas').click()
                expect(page.locator('#integration-check-results')).to_contain_text('Set MONGODB_URI')
                page.locator('#auto-speak').uncheck()
                page.locator('[data-view="patient"]').click()
                page.locator('#demo-button').click()
                expect(page.locator('.candidate')).to_have_count(3)
                page.locator('.candidate').nth(1).click()
                expect(page.locator('#selected-text')).to_have_text('Call my daughter')
                assert server.app.store.state()['requests']==[], 'No request before confirmation'
                page.locator('#confirm-button').click()
                expect(page.locator('#sent-text')).to_have_text('Call my daughter')
                assert server.app.store.state()['metrics']['confirmed']==0,'Demo excluded from real metrics'
                page.locator('#new-button').click()
                page.locator('[data-phrase="water"]').click()
                expect(page.locator('#selected-text')).to_have_text('I need water')
                page.locator('#confirm-button').click()
                expect(page.locator('#sent-text')).to_have_text('I need water')
                care=context.new_page()
                care.goto(url+'/#care')
                real_card=care.locator('.request-card').filter(has=care.get_by_role('heading',name='I need water',exact=True))
                real_card.get_by_role('button',name='Acknowledge',exact=True).click()
                expect(page.locator('#request-status')).to_have_text('Acknowledged by the care team',timeout=7000)
                care.screenshot(path=str(artifacts/'care-desktop.png'),full_page=True)
                real_card.get_by_role('button',name='Mark resolved').click()
                expect(page.locator('#request-status')).to_have_text('Marked resolved by the care team',timeout=7000)
                page.locator('#new-button').click()
                page.locator('.type-card summary').click()
                page.locator('#typed-input').fill('call my dotter')
                page.get_by_role('button',name='Review possible words').click()
                expect(page.locator('.candidate')).to_have_count(2)
                page.locator('.candidate').nth(1).click()
                page.locator('#confirm-button').click()
                expect(page.locator('#sent-text')).to_have_text('call my daughter')
                page.locator('[data-view="insights"]').click()
                expect(page.locator('#memory-list')).to_contain_text('call my daughter')
                page.screenshot(path=str(artifacts/'insights-desktop.png'),full_page=True)
                page.locator('[data-view="settings"]').click()
                page.locator('#profile-name').fill('Jordan')
                page.locator('#profile-room').fill('Bed 03')
                page.get_by_role('button',name='Save preferences').click()
                expect(page.locator('#sidebar-name')).to_have_text('Jordan')
                page.reload()
                expect(page.locator('#profile-name')).to_have_value('Jordan')
                page.locator('[data-view="patient"]').click()
                page.locator('#camera-start').click()
                expect(page.locator('#camera-badge')).to_have_text('Camera active')
                assert awaitless_camera_check(page)
                page.locator('[data-view="teach"]').click()
                expect(page.locator('#view-teach .camera-card')).to_be_visible()
                page.locator('#teach-record').click()
                expect(page.locator('#teach-feedback')).to_contain_text('Saved example',timeout=12000)
                page.reload()
                expect(page.locator('.sample-count').first).to_have_text('1/3')
                # Browser-provided fake video proves capture and persistence, not lip-reading accuracy.
                page.locator('[data-view="patient"]').click()
                page.locator('[data-phrase="cold"]').click()
                page.evaluate('document.getElementById("scan-speed").value="6000"; document.getElementById("scan-speed").dispatchEvent(new Event("input"))')
                page.locator('#scan-toggle').check()
                expect(page.locator('#confirm-button')).to_have_class('button primary scan-focus')
                page.keyboard.press('Space')
                expect(page.locator('#sent-text')).to_have_text('I am cold')
                page.locator('#scan-toggle').uncheck()
                page.locator('#usb-button').click()
                expect(page.locator('#usb-button')).to_have_text('Disconnect controller')
                page.locator('#help-button').click()
                expect(page.locator('#sent-text')).to_have_text('Please help me')
                assert server.app.store.state()['requests'][0]['urgent']==1
                page.wait_for_function('window.serialWrites.some(line=>line.startsWith("STATE|urgent|Please help me"))')
                # Feed a real serial protocol command through the stream reader.
                page.evaluate('window.deviceInput("BACK")')
                expect(page.locator('#interpretation-empty')).to_be_visible()
                # XSS regression: arbitrary names must remain text on every view.
                page.locator('[data-view="settings"]').click()
                page.locator('#profile-name').fill('<img src=x onerror=alert(1)>')
                page.get_by_role('button',name='Save preferences').click()
                expect(page.locator('#sidebar-name img')).to_have_count(0)
                page.locator('[data-view="patient"]').click()
                page.set_viewport_size({'width':390,'height':844})
                page.screenshot(path=str(artifacts/'patient-mobile.png'),full_page=True)
                assert page.evaluate('document.documentElement.scrollWidth <= window.innerWidth'),'Mobile horizontal overflow'
                assert page.evaluate('document.getElementById("camera-stage").getBoundingClientRect().right <= window.innerWidth'),'Camera region overflow'
                blocked=context.request.post(url+'/api/help',data={'confirmed':True},headers={'Origin':'https://example.com'})
                assert blocked.status==403,'Cross-origin mutation rejected'
                invalid=context.request.post(url+'/api/confirm',data={'confirmed':False})
                assert invalid.status==400,'Unconfirmed HTTP mutation rejected'
                server.app.token='test-only-token'
                assert context.request.get(url+'/api/state').status==401
                assert context.request.get(url+'/api/state',headers={'Authorization':'Bearer test-only-token'}).status==200
                server.app.token=''
                testpage=context.new_page()
                testpage.goto(url+'/selftest')
                testpage.wait_for_function('window.testResults')
                result=testpage.evaluate('window.testResults')
                assert not result.get('failed'),result
                assert result['passed']==10,result
                assert not errors,errors
                print('PASS: browser flow, patient/caregiver synchronization, confirmation, demo separation, text correction, profile persistence, webcam capture, training persistence, one-switch controls, help, simulated USB protocol, HTTP origin/auth checks, XSS escaping, mobile layout, 10 recognizer checks')
                browser.close()
        finally:
            server.shutdown()
            server.server_close()
            server.app.store.db.close()


def awaitless_camera_check(page):
    return page.evaluate('document.getElementById("camera").srcObject.getAudioTracks().length === 0')


if __name__=='__main__':
    main()
