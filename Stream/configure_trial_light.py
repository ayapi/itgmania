"""Create the full-canvas Screen-blended trial light in the current OBS scene."""
import os
import time
from pathlib import Path
from obs_sync import OBSWebSocket, settings


def configure(obs):
    name = 'ITGmania 試練ライト'
    scene = obs.call('GetCurrentProgramScene')['currentProgramSceneName']
    video = obs.call('GetVideoSettings')
    url = f'http://127.0.0.1:8765/overlay?mode=light&v={time.time_ns()}'
    sources = {i['inputName']: i for i in obs.call('GetInputList')['inputs']}
    if name in sources and sources[name]['inputKind'] != 'browser_source':
        raise RuntimeError('The trial-light name already belongs to a different source kind')
    browser = dict(url=url, width=video['baseWidth'], height=video['baseHeight'],
                   fps=video['fpsNumerator']//video['fpsDenominator'],
                   shutdown=False, restart_when_active=False)
    items = obs.call('GetSceneItemList', dict(sceneName=scene))['sceneItems']
    existing = next((i for i in items if i['sourceName'] == name), None)
    if name not in sources:
        item_id = obs.call('CreateInput', dict(sceneName=scene, inputName=name,
            inputKind='browser_source', inputSettings=browser,
            sceneItemEnabled=True))['sceneItemId']
    else:
        obs.call('SetInputSettings', dict(inputName=name, inputSettings=browser, overlay=True))
        item_id = existing['sceneItemId'] if existing else obs.call('CreateSceneItem',
            dict(sceneName=scene, sourceName=name, sceneItemEnabled=True))['sceneItemId']
    item = dict(sceneName=scene, sceneItemId=item_id)
    obs.call('SetSceneItemBlendMode', dict(**item, sceneItemBlendMode='OBS_BLEND_SCREEN'))
    # Only touch this dedicated source. All user capture/info transforms stay intact.
    obs.call('SetSceneItemTransform', dict(**item, sceneItemTransform=dict(
        positionX=0, positionY=0, scaleX=1, scaleY=1, rotation=0,
        alignment=5, boundsType='OBS_BOUNDS_NONE', cropLeft=0, cropRight=0,
        cropTop=0, cropBottom=0)))
    if existing is None:
        camera = next((i for i in items if i['sourceName']=='DroidCam OBS'), None)
        obs.call('SetSceneItemIndex', dict(**item,
            sceneItemIndex=camera['sceneItemIndex']+1 if camera else 0))
    obs.call('SetSceneItemEnabled', dict(**item, sceneItemEnabled=True))
    result = obs.call('GetSceneItemBlendMode', item)
    assert result['sceneItemBlendMode'] == 'OBS_BLEND_SCREEN'
    return scene, item_id


if __name__ == '__main__':
    cfg = settings(Path(os.environ['APPDATA'])/'obs-studio/plugin_config/obs-websocket/config.json')
    obs = OBSWebSocket('127.0.0.1', cfg['server_port'], cfg['server_password'])
    try:
        scene, item_id = configure(obs)
        print(f'Trial light configured: Screen blend, full canvas, item {item_id}')
    finally:
        obs.close()
