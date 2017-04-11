import poller
from botocore.vendored.requests.exceptions import ReadTimeout
from botocore.exceptions import ClientError
from task import ActivityTask, DecisionTask
from lib import swf
from daemon import Daemon
from threading import Thread


class Runner(Daemon):

    def __init__(self, workflow, pidfile, worker_count=5):
        super(Runner, self).__init__(pidfile)
        self.workflow = workflow
        self.worker_count = worker_count

    def worker(self):
        while True:
            try:
                task = poller.poll_for_activity_task(
                    self.workflow.domain, {'name': self.workflow.taskList}, self.workflow.name)
                activity_task = ActivityTask(task)
                print 'received activity task %s' % activity_task.activity
                activity = getattr(self.workflow, activity_task.activity)
                result = activity.action(activity_task.input)
                print 'result %s' % result
                swf.respond_activity_task_completed(
                    taskToken=activity_task.task_token, result=result)
            except ReadTimeout as e:
                print "Read timeout while polling", e
            except ClientError as e:
                print "Client error", e
            except ValueError as e:
                print e

    def decider(self):
        while True:
            try:
                task = poller.poll_for_decision_task(
                    self.workflow.domain, {'name': self.workflow.taskList}, self.workflow.name)
                decision_task = DecisionTask(task)
                print 'received decision task %s with input %s' % (decision_task.completed_activity, decision_task.input)
                decisions = self.workflow.decider(decision_task)
                swf.respond_decision_task_completed(
                    taskToken=decision_task.task_token, decisions=decisions)
            except ReadTimeout as e:
                print "Read timeout while polling", e
            except ClientError as e:
                print "Client error", e
            except ValueError as e:
                print e

    def run(self):
        for i in range(0, self.worker_count):
            thread = Thread(target=self.worker)
            thread.setDaemon(True)
            thread.start()
        self.decider()
