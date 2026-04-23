import urllib.request as r, json

def main() -> None:
    post_data = json.dumps({'dashboard': 'Слайд 1. Отчет по операциям репо (1.1)', 'user': 'test_init', 'approver': 'tabladmin', 'params': {'Дата начала периода': '01.01.2025', 'Дата окончания периода': '31.01.2025'}, 'comment': 'API auto-test'}).encode('utf-8')
    req = r.Request('http://localhost:8000/request-freeze', data=post_data, headers={'Content-type': 'application/json'})

    print('\n=== 1. Создаем запрос ===')
    res = json.loads(r.urlopen(req).read())
    print(res)
    task_id = res.get('task_id', '')

    print('\n=== 2. Список PENDING ===')
    res2 = json.loads(r.urlopen('http://localhost:8000/pending-tasks?user=tabladmin').read())
    print('Всего PENDING задач:', len(res2))
    [print(' -', x['TASK_ID'], x['REPORT_NAME']) for x in res2 if x['TASK_ID'] == task_id]

    if task_id:
        print('\n=== 3. Аппрув задачи ===')
        req3 = r.Request(f'http://localhost:8000/approve-task/{task_id}?user=tabladmin', method='POST')
        print(json.loads(r.urlopen(req3).read()))

        print('\n=== 4. Список APPROVED ===')
        res4 = json.loads(r.urlopen('http://localhost:8000/approved-tasks').read())
        print('Всего APPROVED задач:', len(res4))
        [print(' -', x['TASK_ID'], x['REPORT_NAME']) for x in res4 if x['TASK_ID'] == task_id]

        print('\n=== 5. Отменяем задачу ===')
        req5 = r.Request(f'http://localhost:8000/void-task/{task_id}', data=json.dumps({'user':'drp_exp', 'comment': 'roll_back_test'}).encode('utf-8'), headers={'Content-type': 'application/json'}, method='POST')
        print(json.loads(r.urlopen(req5).read()))


if __name__ == '__main__':
    main()
